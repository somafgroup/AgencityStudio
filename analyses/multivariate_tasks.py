"""Worker implementation for immutable multivariate AnalysisRuns."""

from __future__ import annotations

import logging
import time
import uuid

import numpy as np
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from labbridge.multivariate import MultivariateLabError, execute_multivariate_analysis
from projects.models import ProjectActivity

from .models import AnalysisResultArtifact, AnalysisRun, RunErrorCategory, RunStatus
from .multivariate_results import MULTIVARIATE_RESULT_FORMAT
from .multivariate_validation import validate_multivariate_samples
from .sources import SourceContractError, materialize_matrix
from .storage import analysis_storage, write_multivariate_result

logger = logging.getLogger(__name__)


def _locked(run_id) -> AnalysisRun:
    return (
        AnalysisRun.objects.select_for_update()
        .select_related(
            "analysis",
            "analysis__project",
            "system_revision",
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


def _safe_value(value):
    array = np.asarray(value)
    if array.ndim == 0:
        return array.item()
    return array.tolist()


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
        run.save(
            update_fields=("status", "error_category", "error_message", "completed_at")
        )
        _record(
            run,
            "ANALYSIS_RUN_FAILED",
            _("Multivariate Analysis Run %(number)s failed.") % {"number": run.run_number},
        )
    return "failed"


def execute_multivariate_run(run_id: str) -> str:
    """Execute exactly one queued multivariate Run and atomically publish its artifact."""
    started_clock = time.monotonic()
    with transaction.atomic():
        try:
            run = _locked(run_id)
        except AnalysisRun.DoesNotExist:
            return "missing"
        if run.analysis.analysis_kind != "MULTIVARIATE":
            return "wrong-kind"
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
        "analysis.multivariate_run_started run_id=%s analysis_id=%s lab_version=%s",
        run_id,
        run.analysis_id,
        run.agencitylab_version,
    )
    saved_path = None
    try:
        components = list(
            run.components.select_related("observable_definition").order_by("position")
        )
        if not components:
            raise SourceContractError("The immutable multivariate Run has no components.")
        xi, matrix = materialize_matrix(
            dataset_version=run.source_dataset_version,
            prepared_artifact=run.source_prepared_artifact,
            coordinate_position=int(run.mapping_snapshot["time"]["position"]),
            component_positions=[item.source_column_position for item in components],
        )
        validate_multivariate_samples(
            xi,
            matrix,
            component_parameters=[item.parameter_snapshot for item in components],
        )
        call = dict(run.parameter_snapshot.get("call_contract") or {})
        execution = execute_multivariate_analysis(
            u=matrix,
            xi=xi,
            A_ref=call["A_ref"]["value"],
            tau=call["tau"]["value"],
            w=call["w"]["value"],
            P_c=call["P_c"]["value"],
            sample_axis=int(call.get("sample_axis", 0)),
        )
        artifact_id = uuid.uuid4()
        saved_path, serialized = write_multivariate_result(
            result=execution.result,
            run=run,
            artifact_id=artifact_id,
        )
        with transaction.atomic():
            locked = _locked(run_id)
            if locked.status != RunStatus.RUNNING:
                analysis_storage().delete(saved_path)
                return "stale-result"
            if AnalysisResultArtifact.objects.filter(run=locked).exists():
                analysis_storage().delete(saved_path)
                return "already-published"
            AnalysisResultArtifact.objects.create(
                id=artifact_id,
                run=locked,
                storage_path=saved_path,
                format=MULTIVARIATE_RESULT_FORMAT,
                schema_version=serialized.manifest["schema_version"],
                sha256=serialized.sha256,
                size_bytes=serialized.size_bytes,
                manifest=serialized.manifest,
            )
            result = execution.result
            locked.status = RunStatus.COMPLETED
            locked.result_sha256 = serialized.sha256
            locked.effective_context = {
                "A_ref": _safe_value(result.get("A_ref")),
                "tau": _safe_value(result.get("tau")),
                "w": _safe_value(result.get("w")),
                "P_c_components": _safe_value(result.get("P_c_components")),
                "P_c_total": _safe_value(result.get("P_c_total")),
                "aggregation": result.get("aggregation"),
                "scientific_boundary": result.get("scientific_boundary"),
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
                _("Multivariate Analysis Run %(number)s completed.")
                % {"number": locked.run_number},
            )
        logger.info(
            "analysis.multivariate_run_completed run_id=%s analysis_id=%s duration_ms=%s lab_version=%s",
            run_id,
            run.analysis_id,
            round((time.monotonic() - started_clock) * 1000),
            run.agencitylab_version,
        )
        return "completed"
    except MultivariateLabError as exc:
        if saved_path:
            analysis_storage().delete(saved_path)
        logger.warning(
            "analysis.multivariate_run_lab_failed run_id=%s category=%s",
            run_id,
            exc.category,
        )
        return _fail(
            run_id,
            exc.category,
            f"AgencityLab rejected this multivariate configuration: {exc}",
        )
    except (SourceContractError, KeyError, TypeError, ValueError) as exc:
        if saved_path:
            analysis_storage().delete(saved_path)
        return _fail(run_id, RunErrorCategory.SOURCE_ERROR, str(exc))
    except OSError:
        if saved_path:
            try:
                analysis_storage().delete(saved_path)
            except OSError:
                logger.exception("analysis.multivariate_result_cleanup_failed run_id=%s", run_id)
        logger.exception("analysis.multivariate_run_storage_failed run_id=%s", run_id)
        return _fail(
            run_id,
            RunErrorCategory.STORAGE_ERROR,
            _("The multivariate result could not be stored safely."),
        )
    except Exception:
        if saved_path:
            try:
                analysis_storage().delete(saved_path)
            except OSError:
                logger.exception("analysis.multivariate_result_cleanup_failed run_id=%s", run_id)
        logger.exception("analysis.multivariate_run_failed_unexpected run_id=%s", run_id)
        return _fail(
            run_id,
            RunErrorCategory.STUDIO_INTERNAL_ERROR,
            _("The multivariate Analysis Run failed because of an internal Studio error."),
        )
