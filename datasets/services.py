"""Transactional Dataset lifecycle, versioning, storage and permission invariants."""

from __future__ import annotations

import logging
import mimetypes
import uuid
from collections.abc import Iterable
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _

from projects.models import ProjectActivity, ProjectActivityEvent
from workspaces.permissions import (
    can_add_dataset_version,
    can_annotate_dataset,
    can_confirm_dataset_version,
    can_create_dataset,
    can_delete_dataset,
    can_edit_dataset,
    can_view_dataset,
)

from .importers import get_importer
from .models import (
    Dataset,
    DatasetColumn,
    DatasetColumnRole,
    DatasetImportStatus,
    DatasetSourceFormat,
    DatasetSourceKind,
    DatasetVersion,
)
from .storage import dataset_storage

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    ".csv": DatasetSourceFormat.CSV,
    ".tsv": DatasetSourceFormat.TSV,
    ".txt": DatasetSourceFormat.TXT,
    ".xlsx": DatasetSourceFormat.XLSX,
}
_MEDIA_TYPES = {
    DatasetSourceFormat.CSV: "text/csv",
    DatasetSourceFormat.TSV: "text/tab-separated-values",
    DatasetSourceFormat.TXT: "text/plain",
    DatasetSourceFormat.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _clean_dataset_metadata(name: str, description: str) -> tuple[str, str]:
    clean_name = name.strip()
    if not clean_name:
        raise ValidationError(_("Dataset name is required."))
    if len(clean_name) > 180:
        raise ValidationError(_("Dataset name must be 180 characters or fewer."))
    return clean_name, description.strip()


def _unique_dataset_slug(project, name: str) -> str:
    base = slugify(name)[:150] or "dataset"
    candidate = base
    suffix = 2
    while Dataset.objects.filter(project=project, slug=candidate).exists():
        candidate = f"{base[:165]}-{suffix}"
        suffix += 1
        if suffix > 1000:
            raise ValidationError(_("Could not allocate a unique dataset slug."))
    return candidate


def _safe_filename(filename: str) -> str:
    clean = Path(filename or "source").name.replace("\x00", "").strip()
    if not clean:
        clean = "source"
    return clean[:255]


def _source_format(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    try:
        return _SUPPORTED_EXTENSIONS[suffix]
    except KeyError as exc:
        raise ValidationError(
            _("Unsupported dataset format. Upload CSV, TSV, structured TXT or XLSX.")
        ) from exc


def _source_path(*, project_id, dataset_id, version_id, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in _SUPPORTED_EXTENSIONS:
        suffix = ".txt"
    return f"datasets/{project_id}/{dataset_id}/{version_id}/source{suffix}"


def _bounded_chunks(chunks: Iterable[bytes], limit: int):
    total = 0
    for chunk in chunks:
        total += len(chunk)
        if total > limit:
            raise ValidationError(
                _("The dataset source exceeds the configured upload size limit.")
            )
        yield chunk


def _record(project, *, actor, event: str, detail: str = "") -> None:
    ProjectActivity.objects.create(
        project=project,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        event=event,
        detail=detail[:255],
    )


def _enqueue_inspection(version_id, generation: int) -> None:
    from .tasks import inspect_dataset_version

    inspect_dataset_version.delay(str(version_id), generation)


def _create_version_row(
    *,
    dataset: Dataset,
    actor,
    source_kind: str,
    source_format: str,
    source_path: str,
    original_filename: str,
    source_size_bytes: int,
    source_sha256: str,
    media_type: str,
    import_options: dict,
    version_number: int,
    version_id,
) -> DatasetVersion:
    return DatasetVersion.objects.create(
        id=version_id,
        dataset=dataset,
        version_number=version_number,
        source_kind=source_kind,
        source_format=source_format,
        source_path=source_path,
        original_filename=original_filename,
        source_size_bytes=source_size_bytes,
        source_sha256=source_sha256,
        media_type=media_type,
        import_options=dict(import_options or {}),
        created_by=actor,
    )


def _store_source(*, project_id, dataset_id, version_id, filename: str, chunks: Iterable[bytes]):
    storage = dataset_storage()
    path = _source_path(
        project_id=project_id,
        dataset_id=dataset_id,
        version_id=version_id,
        filename=filename,
    )
    return storage.save_chunks(path, chunks)


def create_dataset_from_upload(
    *,
    actor,
    project,
    name: str,
    description: str,
    uploaded_file,
    import_options: dict | None = None,
) -> tuple[Dataset, DatasetVersion]:
    """Store exact uploaded bytes, create Dataset v1, then inspect after commit."""
    if not can_create_dataset(actor, project):
        raise PermissionDenied
    clean_name, clean_description = _clean_dataset_metadata(name, description)
    original_filename = _safe_filename(uploaded_file.name)
    source_format = _source_format(original_filename)
    declared_size = getattr(uploaded_file, "size", None)
    limit = int(settings.DATASET_MAX_UPLOAD_BYTES)
    if declared_size is not None and declared_size > limit:
        raise ValidationError(_("The dataset source exceeds the configured upload size limit."))

    dataset_id = uuid.uuid4()
    version_id = uuid.uuid4()
    storage = dataset_storage()
    path = None
    try:
        path, size, sha256 = _store_source(
            project_id=project.pk,
            dataset_id=dataset_id,
            version_id=version_id,
            filename=original_filename,
            chunks=_bounded_chunks(uploaded_file.chunks(), limit),
        )
        if size == 0:
            raise ValidationError(_("The uploaded dataset source is empty."))
        with transaction.atomic():
            dataset = Dataset.objects.create(
                id=dataset_id,
                project=project,
                name=clean_name,
                slug=_unique_dataset_slug(project, clean_name),
                description=clean_description,
                created_by=actor,
            )
            version = _create_version_row(
                dataset=dataset,
                actor=actor,
                source_kind=DatasetSourceKind.UPLOAD,
                source_format=source_format,
                source_path=path,
                original_filename=original_filename,
                source_size_bytes=size,
                source_sha256=sha256,
                media_type=_MEDIA_TYPES[source_format],
                import_options=import_options or {},
                version_number=1,
                version_id=version_id,
            )
            _record(
                project,
                actor=actor,
                event=ProjectActivityEvent.DATASET_CREATED,
                detail=_("Created dataset %(name)s.") % {"name": dataset.name},
            )
            _record(
                project,
                actor=actor,
                event=ProjectActivityEvent.DATASET_IMPORT,
                detail=_("Started inspection of %(filename)s.")
                % {"filename": original_filename},
            )
            transaction.on_commit(
                lambda: _enqueue_inspection(version.pk, version.inspection_generation)
            )
        return dataset, version
    except Exception:
        if path:
            storage.delete(path)
        raise


def create_dataset_from_paste(
    *,
    actor,
    project,
    name: str,
    description: str,
    source_text: str,
    import_options: dict | None = None,
) -> tuple[Dataset, DatasetVersion]:
    """Persist pasted text as immutable UTF-8 source bytes and inspect it asynchronously."""
    encoded = source_text.encode("utf-8")
    if not encoded:
        raise ValidationError(_("Paste tabular data before importing."))
    if len(encoded) > int(settings.DATASET_MAX_PASTE_BYTES):
        raise ValidationError(_("The pasted dataset exceeds the configured paste size limit."))

    class PasteUpload:
        name = "pasted-data.txt"
        size = len(encoded)

        @staticmethod
        def chunks():
            yield encoded

    options = {"encoding": "utf-8", **dict(import_options or {})}
    dataset, version = create_dataset_from_upload(
        actor=actor,
        project=project,
        name=name,
        description=description,
        uploaded_file=PasteUpload(),
        import_options=options,
    )
    DatasetVersion.objects.filter(pk=version.pk).update(source_kind=DatasetSourceKind.PASTE)
    version.source_kind = DatasetSourceKind.PASTE
    return dataset, version


def add_dataset_version_from_upload(
    *,
    actor,
    dataset: Dataset,
    uploaded_file,
    import_options: dict | None = None,
) -> DatasetVersion:
    """Add immutable raw source bytes without replacing prior DatasetVersions."""
    dataset = Dataset.objects.select_related("project", "project__workspace").get(pk=dataset.pk)
    if not can_add_dataset_version(actor, dataset):
        raise PermissionDenied
    original_filename = _safe_filename(uploaded_file.name)
    source_format = _source_format(original_filename)
    limit = int(settings.DATASET_MAX_UPLOAD_BYTES)
    if getattr(uploaded_file, "size", 0) > limit:
        raise ValidationError(_("The dataset source exceeds the configured upload size limit."))
    version_id = uuid.uuid4()
    storage = dataset_storage()
    path = None
    try:
        path, size, sha256 = _store_source(
            project_id=dataset.project_id,
            dataset_id=dataset.pk,
            version_id=version_id,
            filename=original_filename,
            chunks=_bounded_chunks(uploaded_file.chunks(), limit),
        )
        if size == 0:
            raise ValidationError(_("The uploaded dataset source is empty."))
        with transaction.atomic():
            locked = Dataset.objects.select_for_update().get(pk=dataset.pk)
            duplicate = locked.versions.filter(source_sha256=sha256).order_by("version_number").first()
            if duplicate is not None:
                raise ValidationError(
                    _("These exact source bytes already exist as version %(version)s.")
                    % {"version": duplicate.version_number}
                )
            last_number = (
                locked.versions.order_by("-version_number").values_list("version_number", flat=True).first()
                or 0
            )
            version = _create_version_row(
                dataset=locked,
                actor=actor,
                source_kind=DatasetSourceKind.UPLOAD,
                source_format=source_format,
                source_path=path,
                original_filename=original_filename,
                source_size_bytes=size,
                source_sha256=sha256,
                media_type=_MEDIA_TYPES[source_format],
                import_options=import_options or {},
                version_number=last_number + 1,
                version_id=version_id,
            )
            _record(
                locked.project,
                actor=actor,
                event=ProjectActivityEvent.DATASET_VERSION,
                detail=_("Added dataset %(dataset)s version %(version)s.")
                % {"dataset": locked.name, "version": version.version_number},
            )
            transaction.on_commit(
                lambda: _enqueue_inspection(version.pk, version.inspection_generation)
            )
        return version
    except Exception:
        if path:
            storage.delete(path)
        raise


def get_dataset_or_404(*, user, dataset_id, project=None) -> Dataset:
    queryset = Dataset.objects.select_related(
        "project",
        "project__workspace",
        "created_by",
        "current_version",
    )
    if project is not None:
        queryset = queryset.filter(project=project)
    try:
        dataset = queryset.get(pk=dataset_id)
    except Dataset.DoesNotExist as exc:
        raise Http404 from exc
    if not can_view_dataset(user, dataset):
        raise Http404
    return dataset


@transaction.atomic
def update_dataset(*, actor, dataset: Dataset, name: str, description: str) -> Dataset:
    if not can_edit_dataset(actor, dataset):
        raise PermissionDenied
    clean_name, clean_description = _clean_dataset_metadata(name, description)
    locked = Dataset.objects.select_for_update().select_related("project").get(pk=dataset.pk)
    changed = []
    if locked.name != clean_name:
        locked.name = clean_name
        changed.append("name")
    if locked.description != clean_description:
        locked.description = clean_description
        changed.append("description")
    if changed:
        locked.save(update_fields=(*changed, "updated_at"))
        _record(
            locked.project,
            actor=actor,
            event=ProjectActivityEvent.DATASET_UPDATED,
            detail=_("Updated dataset %(name)s metadata.") % {"name": locked.name},
        )
    return locked


@transaction.atomic
def reprocess_dataset_version(*, actor, version: DatasetVersion, import_options: dict) -> DatasetVersion:
    dataset = Dataset.objects.select_related("project", "project__workspace").get(pk=version.dataset_id)
    if not can_annotate_dataset(actor, dataset):
        raise PermissionDenied
    locked = DatasetVersion.objects.select_for_update().get(pk=version.pk)
    if locked.import_status == DatasetImportStatus.PROCESSING:
        raise ValidationError(_("This dataset version is already being inspected."))
    locked.inspection_generation += 1
    locked.import_status = DatasetImportStatus.PENDING
    locked.import_options = dict(import_options or {})
    locked.failure_summary = ""
    locked.processed_at = None
    locked.save(
        update_fields=(
            "inspection_generation",
            "import_status",
            "import_options",
            "failure_summary",
            "processed_at",
        )
    )
    transaction.on_commit(lambda: _enqueue_inspection(locked.pk, locked.inspection_generation))
    return locked


@transaction.atomic
def update_column_annotations(
    *,
    actor,
    version: DatasetVersion,
    annotations: dict[int, dict],
) -> DatasetVersion:
    dataset = Dataset.objects.select_related("project", "project__workspace").get(pk=version.dataset_id)
    if not can_annotate_dataset(actor, dataset):
        raise PermissionDenied
    locked = DatasetVersion.objects.select_for_update().get(pk=version.pk)
    if locked.import_status != DatasetImportStatus.READY:
        raise ValidationError(_("Wait for dataset inspection to finish before editing columns."))
    columns = {column.position: column for column in locked.columns.select_for_update().all()}
    time_positions = [
        position
        for position, values in annotations.items()
        if values.get("role") == DatasetColumnRole.TIME
    ]
    if len(time_positions) > 1:
        raise ValidationError(_("Select at most one primary time column."))
    for position, values in annotations.items():
        column = columns.get(position)
        if column is None:
            raise ValidationError(_("One of the selected columns no longer exists."))
        role = values.get("role", DatasetColumnRole.OTHER)
        if role not in DatasetColumnRole.values:
            raise ValidationError(_("Unknown dataset column role."))
        unit = str(values.get("unit", "")).strip()
        if len(unit) > 80:
            raise ValidationError(_("Column units must be 80 characters or fewer."))
        column.role = role
        column.unit = unit
    DatasetColumn.objects.bulk_update(columns.values(), ("role", "unit"))
    locked.inspection_generation += 1
    locked.import_status = DatasetImportStatus.PENDING
    locked.failure_summary = ""
    locked.save(update_fields=("inspection_generation", "import_status", "failure_summary"))
    transaction.on_commit(lambda: _enqueue_inspection(locked.pk, locked.inspection_generation))
    return locked


@transaction.atomic
def confirm_dataset_version(*, actor, version: DatasetVersion) -> DatasetVersion:
    dataset = Dataset.objects.select_for_update().select_related("project", "project__workspace").get(
        pk=version.dataset_id
    )
    if not can_confirm_dataset_version(actor, dataset):
        raise PermissionDenied
    locked = DatasetVersion.objects.select_for_update().get(pk=version.pk, dataset=dataset)
    if locked.import_status != DatasetImportStatus.READY:
        raise ValidationError(_("Only a successfully inspected dataset version can be confirmed."))
    locked.confirmed_at = timezone.now()
    locked.confirmed_by = actor
    locked.save(update_fields=("confirmed_at", "confirmed_by"))
    dataset.current_version = locked
    dataset.full_clean()
    dataset.save(update_fields=("current_version", "updated_at"))
    return locked


def preview_page(*, version: DatasetVersion, page: int, page_size: int) -> tuple[list[str], list[list[object]], int]:
    """Return one source-backed preview page without modifying raw values."""
    importer = get_importer(version.source_format)
    page_size = max(1, min(int(page_size), 200))
    page = max(1, int(page))
    offset = (page - 1) * page_size
    with dataset_storage().open(version.source_path, "rb") as handle:
        headers, rows = importer.read_page(
            handle,
            filename=version.original_filename,
            options=dict(version.import_options or {}),
            offset=offset,
            limit=page_size,
        )
    return headers, rows, offset


@transaction.atomic
def delete_dataset(*, actor, dataset: Dataset) -> None:
    locked = Dataset.objects.select_for_update().select_related("project", "project__workspace").get(
        pk=dataset.pk
    )
    if not can_delete_dataset(actor, locked):
        raise PermissionDenied
    source_paths = list(locked.versions.values_list("source_path", flat=True))
    project = locked.project
    name = locked.name
    _record(
        project,
        actor=actor,
        event=ProjectActivityEvent.DATASET_DELETED,
        detail=_("Deleted dataset %(name)s.") % {"name": name},
    )
    locked.delete()

    def cleanup() -> None:
        storage = dataset_storage()
        for path in source_paths:
            try:
                storage.delete(path)
            except OSError:
                logger.exception("dataset.storage_cleanup_failed source_path=%s", path)

    transaction.on_commit(cleanup)


@transaction.atomic
def delete_failed_version(*, actor, version: DatasetVersion) -> None:
    dataset = Dataset.objects.select_for_update().select_related("project", "project__workspace").get(
        pk=version.dataset_id
    )
    if not can_edit_dataset(actor, dataset):
        raise PermissionDenied
    locked = DatasetVersion.objects.select_for_update().get(pk=version.pk, dataset=dataset)
    if locked.import_status != DatasetImportStatus.FAILED:
        raise ValidationError(_("Only failed non-current versions can be removed here."))
    if dataset.current_version_id == locked.pk:
        raise ValidationError(_("The current dataset version cannot be removed."))
    source_path = locked.source_path
    locked.delete()
    transaction.on_commit(lambda: dataset_storage().delete(source_path))


def source_media_type(version: DatasetVersion) -> str:
    return version.media_type or mimetypes.guess_type(version.original_filename)[0] or "application/octet-stream"
