"""Asynchronous raw DatasetVersion inspection tasks."""

from __future__ import annotations

import logging
import time

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from projects.models import ProjectActivity, ProjectActivityEvent

from .importers import get_importer
from .importers.base import ImporterError
from .inspection import inspect_table
from .models import DatasetColumn, DatasetImportStatus, DatasetVersion
from .storage import dataset_storage

logger = logging.getLogger(__name__)


def _activity(version: DatasetVersion, event: str, detail: str) -> None:
    ProjectActivity.objects.create(
        project=version.dataset.project,
        actor=version.created_by,
        event=event,
        detail=detail[:255],
    )


def _locked_version(version_id: str) -> DatasetVersion:
    """Lock the version row without locking nullable related records."""
    return (
        DatasetVersion.objects.select_for_update(of=("self",))
        .select_related("dataset", "dataset__project")
        .get(pk=version_id)
    )


@shared_task(name="datasets.inspect_dataset_version")
def inspect_dataset_version(version_id: str, generation: int) -> str:
    """Inspect an immutable raw source without preprocessing or scientific inference."""
    started = time.monotonic()
    with transaction.atomic():
        try:
            version = _locked_version(version_id)
        except DatasetVersion.DoesNotExist:
            return "missing"
        if version.inspection_generation != generation:
            return "stale"
        if version.import_status == DatasetImportStatus.PROCESSING:
            return "already-processing"
        if version.import_status in {DatasetImportStatus.READY, DatasetImportStatus.FAILED}:
            return "already-finished"
        version.import_status = DatasetImportStatus.PROCESSING
        version.failure_summary = ""
        version.save(update_fields=("import_status", "failure_summary"))
        annotations = {
            column.position: {"role": column.role, "unit": column.unit}
            for column in version.columns.all()
        }
        source_path = version.source_path
        source_format = version.source_format
        filename = version.original_filename
        options = dict(version.import_options or {})

    logger.info(
        "dataset.import_started version_id=%s dataset_id=%s importer_format=%s",
        version_id,
        version.dataset_id,
        source_format,
    )
    try:
        storage = dataset_storage()
        if not storage.exists(source_path):
            raise ImporterError("The stored dataset source is unexpectedly missing.")
        importer = get_importer(source_format)
        with storage.open(source_path, "rb") as handle:
            table = importer.open_table(handle, filename=filename, options=options)
            result = inspect_table(table, annotations=annotations)
    except ImporterError as exc:
        failure = str(exc)[:500] or _("The dataset source could not be inspected.")
        logger.warning(
            "dataset.import_failed version_id=%s dataset_id=%s reason=%s",
            version_id,
            version.dataset_id,
            exc.__class__.__name__,
        )
        with transaction.atomic():
            try:
                locked = _locked_version(version_id)
            except DatasetVersion.DoesNotExist:
                return "missing-after-failure"
            if locked.inspection_generation != generation:
                return "stale-failure"
            locked.import_status = DatasetImportStatus.FAILED
            locked.failure_summary = failure
            locked.processed_at = timezone.now()
            locked.save(update_fields=("import_status", "failure_summary", "processed_at"))
            _activity(
                locked,
                ProjectActivityEvent.DATASET_FAILED,
                _("Dataset %(name)s version %(version)s import failed.")
                % {"name": locked.dataset.name, "version": locked.version_number},
            )
        return "failed"
    except Exception:
        logger.exception(
            "dataset.import_failed_unexpected version_id=%s dataset_id=%s",
            version_id,
            version.dataset_id,
        )
        with transaction.atomic():
            try:
                locked = _locked_version(version_id)
            except DatasetVersion.DoesNotExist:
                return "missing-after-failure"
            if locked.inspection_generation != generation:
                return "stale-failure"
            locked.import_status = DatasetImportStatus.FAILED
            locked.failure_summary = _("The dataset source could not be inspected.")
            locked.processed_at = timezone.now()
            locked.save(update_fields=("import_status", "failure_summary", "processed_at"))
            _activity(
                locked,
                ProjectActivityEvent.DATASET_FAILED,
                _("Dataset %(name)s version %(version)s import failed.")
                % {"name": locked.dataset.name, "version": locked.version_number},
            )
        return "failed"

    with transaction.atomic():
        try:
            locked = _locked_version(version_id)
        except DatasetVersion.DoesNotExist:
            return "missing-after-inspection"
        if locked.inspection_generation != generation:
            return "stale-result"
        locked.columns.all().delete()
        DatasetColumn.objects.bulk_create(
            [DatasetColumn(dataset_version=locked, **column) for column in result["columns"]]
        )
        locked.importer_id = importer.importer_id
        locked.importer_schema_version = importer.schema_version
        locked.import_options = result["used_options"]
        locked.detected_options = result["detected_options"]
        locked.row_count = result["row_count"]
        locked.column_count = result["column_count"]
        locked.inspection_summary = result["summary"]
        locked.quality_issues = result["issues"]
        locked.failure_summary = ""
        locked.import_status = DatasetImportStatus.READY
        locked.processed_at = timezone.now()
        locked.save(
            update_fields=(
                "importer_id",
                "importer_schema_version",
                "import_options",
                "detected_options",
                "row_count",
                "column_count",
                "inspection_summary",
                "quality_issues",
                "failure_summary",
                "import_status",
                "processed_at",
            )
        )
        _activity(
            locked,
            ProjectActivityEvent.DATASET_READY,
            _("Dataset %(name)s version %(version)s is ready for review.")
            % {"name": locked.dataset.name, "version": locked.version_number},
        )
    logger.info(
        "dataset.import_succeeded version_id=%s dataset_id=%s rows=%s columns=%s duration_ms=%s",
        version_id,
        version.dataset_id,
        result["row_count"],
        result["column_count"],
        round((time.monotonic() - started) * 1000),
    )
    return "ready"


# Celery autodiscovery imports this module. Importing the preparation task here registers it too.
from .preparation_tasks import execute_data_preparation  # noqa: F401
