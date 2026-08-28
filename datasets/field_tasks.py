"""Celery inspection for immutable NPZ observable-field sources."""

from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction
from django.utils.translation import gettext as _

from projects.models import ProjectActivity, ProjectActivityEvent

from .field_source import FIELD_SOURCE_IMPORTER, FieldSourceError, inspect_npz_source
from .models import DatasetImportStatus, DatasetVersion
from .storage import dataset_storage

logger = logging.getLogger(__name__)


def _record(version: DatasetVersion, event: str, detail: str) -> None:
    ProjectActivity.objects.create(
        project=version.dataset.project,
        actor=version.created_by,
        event=event,
        detail=detail[:255],
    )


@shared_task(name="datasets.inspect_field_dataset_version")
def inspect_field_dataset_version(version_id: str, generation: int = 0) -> str:
    """Inspect one exact NPZ source while preserving its original bytes."""

    with transaction.atomic():
        try:
            version = (
                DatasetVersion.objects.select_for_update()
                .select_related("dataset", "dataset__project")
                .get(pk=version_id)
            )
        except (DatasetVersion.DoesNotExist, ValueError):
            return "missing"
        if int(version.inspection_generation) != int(generation):
            return "stale"
        if version.import_status == DatasetImportStatus.PROCESSING:
            return "already-processing"
        if version.import_status == DatasetImportStatus.READY:
            return "already-ready"
        version.import_status = DatasetImportStatus.PROCESSING
        version.failure_summary = ""
        version.save(update_fields=("import_status", "failure_summary"))

    try:
        storage = dataset_storage()
        if not storage.exists(version.source_path):
            raise FieldSourceError("The immutable NPZ source is missing from private storage.")
        with storage.open(version.source_path, "rb") as handle:
            summary = inspect_npz_source(handle)
    except (FieldSourceError, OSError) as exc:
        with transaction.atomic():
            locked = DatasetVersion.objects.select_for_update().select_related(
                "dataset", "dataset__project"
            ).get(pk=version_id)
            if int(locked.inspection_generation) != int(generation):
                return "stale-failure"
            locked.import_status = DatasetImportStatus.FAILED
            locked.failure_summary = str(exc)[:500]
            locked.save(update_fields=("import_status", "failure_summary"))
            _record(locked, ProjectActivityEvent.DATASET_FAILED, _("Field source inspection failed."))
        return "failed"
    except Exception:
        logger.exception("dataset.field_inspection_failed version_id=%s", version_id)
        with transaction.atomic():
            locked = DatasetVersion.objects.select_for_update().select_related(
                "dataset", "dataset__project"
            ).get(pk=version_id)
            if int(locked.inspection_generation) != int(generation):
                return "stale-failure"
            locked.import_status = DatasetImportStatus.FAILED
            locked.failure_summary = _("The field source could not be inspected safely.")
            locked.save(update_fields=("import_status", "failure_summary"))
            _record(locked, ProjectActivityEvent.DATASET_FAILED, _("Field source inspection failed."))
        return "failed"

    with transaction.atomic():
        locked = DatasetVersion.objects.select_for_update().select_related(
            "dataset", "dataset__project"
        ).get(pk=version_id)
        if int(locked.inspection_generation) != int(generation):
            return "stale-result"
        locked.import_status = DatasetImportStatus.READY
        locked.importer_id = FIELD_SOURCE_IMPORTER
        locked.inspection_summary = summary
        locked.quality_issues = []
        locked.row_count = None
        locked.column_count = None
        locked.failure_summary = ""
        locked.save(
            update_fields=(
                "import_status",
                "importer_id",
                "inspection_summary",
                "quality_issues",
                "row_count",
                "column_count",
                "failure_summary",
            )
        )
        _record(
            locked,
            ProjectActivityEvent.DATASET_READY,
            _("Immutable NPZ field source inspected and ready for explicit axis mapping."),
        )
    return "ready"
