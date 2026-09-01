"""Celery execution for immutable EXPERIMENTAL observable spatial field Runs."""

from __future__ import annotations

import logging
import time
import uuid

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from datasets.field_source import FieldSourceError
from labbridge.fields import ObservableFieldLabError, execute_observable_field_analysis
from projects.models import ProjectActivity

from .field_sources import materialize_field_run
from .field_storage import write_observable_field_result
from .models import AnalysisResultArtifact, AnalysisRun, RunErrorCategory, RunStatus
from .storage import analysis_storage

logger = logging.getLogger(__name__)


def _locked(run_id):
    return (
        AnalysisRun.objects.select_for_update()
        .select_related("analysis", "analysis__project")
        .get(pk=run_id)
    )


def _record(run, event: str, detail: str) -> None:
    ProjectActivity.objects.create(
        project=run.analysis.project,
        actor=run.created_by,
        event=event,
        detail=detail[:255],
    )


def _fail(run_id, category: str, message: str) -> str:
    with transaction.atomic():
        try:
            run = _locked(run_id)
        except AnalysisRun.DoesNotExist:
            return "missing-after-failure"
        if run.status != RunStatus.RUNNING:
            return "stale-failure"
        run.status = RunStatus.FAILED
        run.error_category = category
        run.error_message = str(message)[:500]
        run.completed_at = timezone.now()
        run.save(update_fields=("status", "error_category", "error_message", "completed_at"))
        _record(
            run,
            "ANALYSIS_RUN_FAILED",
            _("Observable field Run %(number)s failed.") % {"number": run.run_number},
        )
    return "failed"


def execute_observable_field_run(run_id: str) -> str:
    """Execute one frozen field Run through the public AgencityLab field API."""

    started_clock = time.monotonic()
    with transaction.atomic():
        try:
            run = _locked(run_id)
        except (AnalysisRun.DoesNotExist, ValueError):
            return "missing"
        if run.status == RunStatus.RUNNING:
            return "already-running"
        if run.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}:
            return "already-finished"
        if run.status != RunStatus.QUEUED:
            return "not-queued"
        run.status = RunStatus.RUNNING
        run.started_at = timezone.now()
        run.error_category = ""
        run.error_message = ""
        run.save(update_fields=("status", "started_at", "error_category", "error_message"))

    saved_path = None
    try:
        inputs = materialize_field_run(run)
        execution = execute_observable_field_analysis(
            u=inputs.u,
            t=inputs.t,
            spatial_axes=inputs.spatial_axes,
            A_ref=inputs.A_ref,
            tau=inputs.tau,
            w=inputs.w,
            P_c=inputs.P_c,
            time_axis=inputs.time_axis,
            metadata={
                "source": f"AgencityStudio AnalysisRun {run.pk}",
                "source_sha256": run.source_sha256,
                "observable": run.mapping_snapshot.get("u", {}).get("observable_name", ""),
                "observable_unit": run.mapping_snapshot.get("u", {}).get("unit", ""),
                "time_unit": run.mapping_snapshot.get("time", {}).get("unit", ""),
            },
        )
        result = execution.result
        artifact_id = uuid.uuid4()
        saved_path, serialized = write_observable_field_result(
            result=result, run=run, artifact_id=artifact_id
        )
        with transaction.atomic():
            locked = _locked(run_id)
            if locked.status != RunStatus.RUNNING:
                analysis_storage().delete(saved_path)
                return "stale-result"
            AnalysisResultArtifact.objects.create(
                id=artifact_id,
                run=locked,
                storage_path=saved_path,
                format="ZIP_NPY_JSON",
                schema_version=serialized.manifest["schema_version"],
                sha256=serialized.sha256,
                size_bytes=serialized.size_bytes,
                manifest=serialized.manifest,
            )
            locked.status = RunStatus.COMPLETED
            locked.result_sha256 = serialized.sha256
            locked.effective_context = {
                "scientific_status": "EXPERIMENTAL",
                "field_shape": list(result.u.shape),
                "spatial_shape": list(result.spatial_shape),
                "time_axis": int(result.time_axis),
                "requested_w_mode": locked.parameter_snapshot["w"].get("mode"),
                "lab_w_mode": result.metadata.get("w_mode"),
                "lab_w_resolution": result.metadata.get("w_resolution"),
                "resolved_w_shape": list(result.w.shape),
                "crm_scope": result.metadata.get("crm_scope"),
            }
            locked.warnings = [*locked.warnings, *execution.warnings]
            locked.completed_at = timezone.now()
            locked.save(
                update_fields=(
                    "status",
                    "result_sha256",
                    "effective_context",
                    "warnings",
                    "completed_at",
                )
            )
            _record(
                locked,
                "ANALYSIS_RUN_COMPLETED",
                _("Observable field Run %(number)s completed.") % {"number": locked.run_number},
            )
        logger.info(
            "analysis.field_run_completed run_id=%s duration_ms=%s lab_version=%s",
            run_id,
            round((time.monotonic() - started_clock) * 1000),
            run.agencitylab_version,
        )
        return "completed"
    except ObservableFieldLabError as exc:
        if saved_path:
            analysis_storage().delete(saved_path)
        return _fail(run_id, exc.category, f"AgencityLab rejected this field configuration: {exc}")
    except FieldSourceError as exc:
        if saved_path:
            analysis_storage().delete(saved_path)
        return _fail(run_id, RunErrorCategory.SOURCE_ERROR, str(exc))
    except OSError:
        if saved_path:
            try:
                analysis_storage().delete(saved_path)
            except OSError:
                logger.exception("analysis.field_result_cleanup_failed run_id=%s", run_id)
        logger.exception("analysis.field_storage_failed run_id=%s", run_id)
        return _fail(run_id, RunErrorCategory.STORAGE_ERROR, _("The observable field result could not be stored safely."))
    except Exception:
        if saved_path:
            try:
                analysis_storage().delete(saved_path)
            except OSError:
                logger.exception("analysis.field_result_cleanup_failed run_id=%s", run_id)
        logger.exception("analysis.field_run_failed_unexpected run_id=%s", run_id)
        return _fail(
            run_id,
            RunErrorCategory.STUDIO_INTERNAL_ERROR,
            _("The observable field Run failed because of an internal Studio error."),
        )
