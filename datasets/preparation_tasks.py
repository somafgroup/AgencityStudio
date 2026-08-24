"""Celery execution for immutable prepared-data materializations."""

from __future__ import annotations

import logging
import time
import uuid

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from projects.models import ProjectActivity, ProjectActivityEvent

from .models import DataPreparation, DataPreparationStatus, PreparedDataArtifact
from .preparation import (
    PreparationError,
    apply_recipe,
    csv_chunks,
    inspect_prepared_table,
    load_source_table,
)
from .preparation_services import preparation_artifact_path
from .storage import dataset_storage

logger = logging.getLogger(__name__)


def _locked(preparation_id: str) -> DataPreparation:
    return (
        DataPreparation.objects.select_for_update()
        .select_related(
            "source_version",
            "source_version__dataset",
            "source_version__dataset__project",
        )
        .prefetch_related("source_version__columns")
        .get(pk=preparation_id)
    )


def _activity(preparation: DataPreparation, event: str, detail: str) -> None:
    ProjectActivity.objects.create(
        project=preparation.source_version.dataset.project,
        actor=preparation.created_by,
        event=event,
        detail=detail[:255],
    )


def _mark_failed(preparation_id: str, message: str) -> str:
    with transaction.atomic():
        try:
            locked = _locked(preparation_id)
        except DataPreparation.DoesNotExist:
            return "missing-after-failure"
        if locked.status != DataPreparationStatus.PROCESSING:
            return "stale-failure"
        locked.status = DataPreparationStatus.FAILED
        locked.failure_summary = message[:500]
        locked.finished_at = timezone.now()
        locked.save(update_fields=("status", "failure_summary", "finished_at", "updated_at"))
        _activity(
            locked,
            ProjectActivityEvent.PREP_FAILED,
            _("Preparation %(name)s failed.") % {"name": locked.name},
        )
    return "failed"


@shared_task(name="datasets.execute_data_preparation")
def execute_data_preparation(preparation_id: str) -> str:
    """Execute one frozen ordered recipe and publish an immutable result atomically."""
    started_clock = time.monotonic()
    with transaction.atomic():
        try:
            preparation = _locked(preparation_id)
        except DataPreparation.DoesNotExist:
            return "missing"
        if preparation.status == DataPreparationStatus.PROCESSING:
            return "already-processing"
        if preparation.status in {DataPreparationStatus.READY, DataPreparationStatus.FAILED}:
            return "already-finished"
        if preparation.status != DataPreparationStatus.QUEUED:
            return "not-queued"
        preparation.status = DataPreparationStatus.PROCESSING
        preparation.started_at = timezone.now()
        preparation.failure_summary = ""
        preparation.save(
            update_fields=("status", "started_at", "failure_summary", "updated_at")
        )
        _activity(
            preparation,
            ProjectActivityEvent.PREP_STARTED,
            _("Started preparation %(name)s.") % {"name": preparation.name},
        )
        source_rows = preparation.source_version.row_count
        recipe = list(preparation.recipe)

    logger.info(
        "dataset.preparation_started preparation_id=%s source_version_id=%s operations=%s",
        preparation_id,
        preparation.source_version_id,
        [step.get("operation") for step in recipe],
    )
    saved_path = None
    try:
        table = load_source_table(preparation.source_version)
        table, warnings = apply_recipe(table, recipe)
        inspection, column_metadata = inspect_prepared_table(table)
        artifact_id = uuid.uuid4()
        path = preparation_artifact_path(preparation, artifact_id)
        storage = dataset_storage()
        saved_path, size_bytes, prepared_sha256 = storage.save_chunks(path, csv_chunks(table))
        duration_ms = round((time.monotonic() - started_clock) * 1000)
        with transaction.atomic():
            try:
                locked = _locked(preparation_id)
            except DataPreparation.DoesNotExist:
                storage.delete(saved_path)
                return "missing-after-execution"
            if locked.status != DataPreparationStatus.PROCESSING:
                storage.delete(saved_path)
                return "stale-result"
            PreparedDataArtifact.objects.create(
                id=artifact_id,
                preparation=locked,
                storage_path=saved_path,
                output_format="CSV",
                media_type="text/csv",
                size_bytes=size_bytes,
                prepared_sha256=prepared_sha256,
                row_count=len(table.rows),
                column_count=len(table.columns),
                column_metadata=column_metadata,
                inspection_summary=inspection["summary"],
                quality_issues=inspection["issues"],
            )
            locked.status = DataPreparationStatus.READY
            locked.warnings = warnings
            locked.failure_summary = ""
            locked.finished_at = timezone.now()
            locked.execution_metadata = {
                "duration_ms": duration_ms,
                "source_rows": source_rows,
                "output_rows": len(table.rows),
                "output_columns": len(table.columns),
                "operation_count": len(recipe),
                "output_format": "CSV",
                "csv_encoding": "utf-8",
                "csv_delimiter": ",",
                "csv_line_ending": "LF",
            }
            locked.save(
                update_fields=(
                    "status",
                    "warnings",
                    "failure_summary",
                    "finished_at",
                    "execution_metadata",
                    "updated_at",
                )
            )
            _activity(
                locked,
                ProjectActivityEvent.PREP_READY,
                _("Prepared data %(name)s is ready.") % {"name": locked.name},
            )
        logger.info(
            "dataset.preparation_succeeded preparation_id=%s source_version_id=%s rows=%s columns=%s duration_ms=%s",
            preparation_id,
            preparation.source_version_id,
            len(table.rows),
            len(table.columns),
            duration_ms,
        )
        return "ready"
    except PreparationError as exc:
        if saved_path:
            dataset_storage().delete(saved_path)
        logger.warning(
            "dataset.preparation_failed preparation_id=%s source_version_id=%s reason=%s",
            preparation_id,
            preparation.source_version_id,
            exc.__class__.__name__,
        )
        return _mark_failed(preparation_id, str(exc) or _("The preparation could not be completed."))
    except Exception:
        if saved_path:
            try:
                dataset_storage().delete(saved_path)
            except OSError:
                logger.exception("dataset.preparation_cleanup_failed path=%s", saved_path)
        logger.exception(
            "dataset.preparation_failed_unexpected preparation_id=%s source_version_id=%s",
            preparation_id,
            preparation.source_version_id,
        )
        return _mark_failed(preparation_id, _("The preparation could not be completed."))
