"""Celery execution for immutable AnalysisRuns."""

from __future__ import annotations

import logging
import time
import uuid

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from labbridge.execution import CanonicalLabError, execute_canonical_analysis
from projects.models import ProjectActivity

from .models import AnalysisKind, AnalysisResultArtifact, AnalysisRun, RunErrorCategory, RunStatus
from .sources import SourceContractError, materialize_vectors
from .storage import analysis_storage, write_analysis_result
from .validation import validate_sample_contract

logger = logging.getLogger(__name__)


def _locked(run_id) -> AnalysisRun:
    """Lock the Run row without outer-joining its mutually exclusive nullable sources."""
    return (
        AnalysisRun.objects.select_for_update()
        .select_related(
            "analysis",
            "analysis__project",
            "system_revision",
            "system_observable",
        )
        .get(pk=run_id)
    )


def _record(run: AnalysisRun, event: str, detail: str) -> None:
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
        _record(run, "ANALYSIS_RUN_FAILED", _("Analysis Run %(number)s failed.") % {"number": run.run_number})
    return "failed"


@shared_task(name="analyses.execute_analysis_run")
def execute_analysis_run(run_id: str) -> str:
    """Execute one frozen Run using the public Lab contract selected by its Analysis kind."""
    try:
        kind = AnalysisRun.objects.filter(pk=run_id).values_list(
            "analysis__analysis_kind", flat=True
        ).first()
    except (TypeError, ValueError):
        return "missing"
    if kind == AnalysisKind.MULTIVARIATE:
        from .multivariate_tasks import execute_multivariate_run

        return execute_multivariate_run(run_id)

    started_clock = time.monotonic()
    with transaction.atomic():
        try:
            run = _locked(run_id)
        except AnalysisRun.DoesNotExist:
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

    logger.info(
        "analysis.run_started run_id=%s analysis_id=%s lab_version=%s",
        run_id,
        run.analysis_id,
        run.agencitylab_version,
    )
    saved_path = None
    try:
        time_mapping = run.mapping_snapshot["time"]
        observable_mapping = run.mapping_snapshot["observable"]
        xi, u = materialize_vectors(
            dataset_version=run.source_dataset_version,
            prepared_artifact=run.source_prepared_artifact,
            coordinate_position=int(time_mapping["position"]),
            observable_position=int(observable_mapping["position"]),
        )
        params = run.parameter_snapshot
        requested_w = params["w"].get("requested_value")
        validate_sample_contract(
            xi,
            u,
            requested_w=requested_w,
            tau=float(params["tau"]["value"]),
        )
        options = run.analysis_options or {}
        execution = execute_canonical_analysis(
            u=u,
            xi=xi,
            A_ref=float(params["A_ref"]["value"]),
            tau=float(params["tau"]["value"]),
            w=None if params["w"].get("mode") == "UNSPECIFIED" else float(requested_w),
            P_c=float(params["P_c"]["value"]),
            unit=str(observable_mapping.get("unit", "")),
            coordinate_unit=str(time_mapping.get("unit", "")),
            power_unit=str(params["P_c"].get("unit", "")),
            observable_kind=run.system_observable.observable_kind,
            domain=str(options.get("domain", "")),
            mechanism=str(options.get("mechanism", "")),
            system_type=str(options.get("system_type", "")),
            environment=str(options.get("environment", "")),
            geometry=str(options.get("geometry", "")),
            metadata={
                "coordinate_name": time_mapping.get("display_name") or time_mapping.get("source_name") or "xi",
                "signal_name": observable_mapping.get("display_name") or observable_mapping.get("source_name") or "u",
                "source": f"AgencityStudio AnalysisRun {run.pk}",
            },
        )
        artifact_id = uuid.uuid4()
        saved_path, serialized = write_analysis_result(result=execution.result, run=run, artifact_id=artifact_id)
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
                "A_ref": float(execution.result.A_ref),
                "tau": float(execution.result.tau),
                "requested_w": requested_w,
                "requested_w_mode": params["w"].get("mode"),
                "effective_w": execution.result.memory_window,
                "P_c": float(execution.result.P_c),
            }
            locked.warnings = [*locked.warnings, *execution.warnings]
            locked.completed_at = timezone.now()
            locked.save(update_fields=("status", "result_sha256", "effective_context", "warnings", "completed_at"))
            _record(locked, "ANALYSIS_RUN_COMPLETED", _("Analysis Run %(number)s completed.") % {"number": locked.run_number})
        logger.info(
            "analysis.run_completed run_id=%s analysis_id=%s duration_ms=%s lab_version=%s",
            run_id,
            run.analysis_id,
            round((time.monotonic() - started_clock) * 1000),
            run.agencitylab_version,
        )
        return "completed"
    except CanonicalLabError as exc:
        if saved_path:
            analysis_storage().delete(saved_path)
        logger.warning("analysis.run_lab_failed run_id=%s category=%s", run_id, exc.category)
        return _fail(run_id, exc.category, f"AgencityLab rejected this configuration: {exc}")
    except SourceContractError as exc:
        if saved_path:
            analysis_storage().delete(saved_path)
        return _fail(run_id, RunErrorCategory.SOURCE_ERROR, str(exc))
    except OSError:
        if saved_path:
            try:
                analysis_storage().delete(saved_path)
            except OSError:
                logger.exception("analysis.result_cleanup_failed run_id=%s", run_id)
        logger.exception("analysis.run_storage_failed run_id=%s", run_id)
        return _fail(run_id, RunErrorCategory.STORAGE_ERROR, _("The canonical result could not be stored safely."))
    except Exception:
        if saved_path:
            try:
                analysis_storage().delete(saved_path)
            except OSError:
                logger.exception("analysis.result_cleanup_failed run_id=%s", run_id)
        logger.exception("analysis.run_failed_unexpected run_id=%s", run_id)
        return _fail(run_id, RunErrorCategory.STUDIO_INTERNAL_ERROR, _("The Analysis Run failed because of an internal Studio error."))
