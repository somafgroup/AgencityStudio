"""Dataset lifecycle for immutable N-dimensional NPZ field sources."""

from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils.text import slugify
from django.utils.translation import gettext as _

from projects.models import ProjectActivity, ProjectActivityEvent
from workspaces.permissions import can_create_dataset

from .field_source import FIELD_SOURCE_FORMAT
from .models import Dataset, DatasetSourceKind, DatasetVersion
from .storage import dataset_storage


def _slug(project, name: str) -> str:
    base = slugify(name)[:150] or "field-dataset"
    candidate = base
    suffix = 2
    while Dataset.objects.filter(project=project, slug=candidate).exists():
        candidate = f"{base[:165]}-{suffix}"
        suffix += 1
    return candidate


def _bounded_chunks(uploaded_file):
    limit = min(
        int(settings.DATASET_MAX_UPLOAD_BYTES),
        int(getattr(settings, "FIELD_MAX_UPLOAD_BYTES", settings.DATASET_MAX_UPLOAD_BYTES)),
    )
    total = 0
    for chunk in uploaded_file.chunks():
        total += len(chunk)
        if total > limit:
            raise ValidationError(_("The field source exceeds the configured upload size limit."))
        yield chunk


def _enqueue(version_id, generation: int) -> None:
    from .field_tasks import inspect_field_dataset_version

    inspect_field_dataset_version.delay(str(version_id), generation)


@transaction.atomic
def create_field_dataset_from_upload(
    *, actor, project, name: str, description: str, uploaded_file
) -> tuple[Dataset, DatasetVersion]:
    """Store exact NPZ bytes and queue safe N-dimensional source inspection."""

    if not can_create_dataset(actor, project):
        raise PermissionDenied
    clean_name = str(name).strip()
    if not clean_name:
        raise ValidationError(_("Dataset name is required."))
    if len(clean_name) > 180:
        raise ValidationError(_("Dataset name must be 180 characters or fewer."))
    filename = Path(getattr(uploaded_file, "name", "field.npz")).name[:255]
    if Path(filename).suffix.lower() != ".npz":
        raise ValidationError(_("Observable field sources must be uploaded as NPZ files."))

    dataset_id = uuid.uuid4()
    version_id = uuid.uuid4()
    source_path = f"datasets/{project.pk}/{dataset_id}/{version_id}/source.npz"
    storage = dataset_storage()
    try:
        stored_path, size, digest = storage.save_chunks(
            source_path, _bounded_chunks(uploaded_file)
        )
        dataset = Dataset.objects.create(
            id=dataset_id,
            project=project,
            name=clean_name,
            slug=_slug(project, clean_name),
            description=str(description).strip(),
            created_by=actor,
        )
        version = DatasetVersion.objects.create(
            id=version_id,
            dataset=dataset,
            version_number=1,
            source_kind=DatasetSourceKind.UPLOAD,
            source_format=FIELD_SOURCE_FORMAT,
            source_path=stored_path,
            original_filename=filename,
            source_size_bytes=size,
            source_sha256=digest,
            media_type="application/x-npz",
            import_options={"field_source": True, "container": "NPZ"},
            created_by=actor,
        )
    except Exception:
        try:
            storage.delete(source_path)
        except OSError:
            pass
        raise

    ProjectActivity.objects.create(
        project=project,
        actor=actor,
        event=ProjectActivityEvent.DATASET_CREATED,
        detail=_("Created observable field dataset %(name)s.") % {"name": dataset.name},
    )
    ProjectActivity.objects.create(
        project=project,
        actor=actor,
        event=ProjectActivityEvent.DATASET_IMPORT,
        detail=_("Started immutable NPZ field source inspection."),
    )
    transaction.on_commit(lambda: _enqueue(version.pk, version.inspection_generation))
    return dataset, version
