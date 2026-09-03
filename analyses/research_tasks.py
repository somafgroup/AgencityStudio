"""Celery execution for immutable autonomous RESEARCH field Runs."""

from __future__ import annotations

import logging
import time
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from labbridge.research import ResearchLabError, execute_research_dynamics
from projects.models import ProjectActivity

from .models import AnalysisResultArtifact, AnalysisRun, RunErrorCategory, RunStatus
from .research_storage import (
    open_research_input_reader,
    write_research_result,
)
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
            _("RESEARCH field Run %(number)s failed.") % {"number": run.run_number},
        )
    return "failed"


def execute_research_field_run(run_id: str) -> str:
    """Execute one frozen Run through one exact public AgencityLab research solver."""

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
        with open_research_input_reader(run, verify_hash=True) as reader:
            manifest = reader.read_manifest()
            phi0 = reader.read_series("phi0")
            phi_dot0 = reader.read_series("phi_dot0") if "phi_dot0" in reader.available_series else None
            axes = tuple(
                reader.read_series(f"spatial_axis_{index}")
                for index in range(len(manifest["spatial_shape"]))
            )
        params = run.parameter_snapshot
        options = run.analysis_options
        boundary = dict(options["boundary"]["value"])
        boundary_value = complex(float(boundary["real"]), float(boundary["imag"]))
        if boundary_value.imag == 0.0:
            boundary_value = boundary_value.real
        post = dict(options.get("postprocessors") or {})
        execution = execute_research_dynamics(
            model=options["model"],
            phi0=phi0,
            phi_dot0=phi_dot0,
            axes=axes,
            lambda_=float(params["lambda"]["value"]),
            mu=float(params["mu"]["value"]),
            gamma=(None if params["gamma"]["value"] is None else float(params["gamma"]["value"])),
            dt_solver=float(options["numerical_method"]["dt_solver"]),
            n_steps=int(options["numerical_method"]["n_steps"]),
            boundary_kind=options["boundary"]["kind"],
            boundary_value=boundary_value,
            metadata={
                "source": f"AgencityStudio AnalysisRun {run.pk}",
                "input_sha256": run.source_sha256,
                "scientific_status": "RESEARCH",
            },
            topology_contour_indices=tuple(post.get("topology_contour_indices") or ()),
            thermo_t_eff=post.get("thermo_t_eff"),
            thermo_entropy_a=post.get("thermo_entropy_a"),
        )
        artifact_id = uuid.uuid4()
        saved_path, serialized = write_research_result(
            execution=execution, run=run, artifact_id=artifact_id
        )
        max_output = int(settings.RESEARCH_FIELD_MAX_OUTPUT_BYTES)
        if serialized.size_bytes > max_output:
            analysis_storage().delete(saved_path)
            saved_path = None
            return _fail(
                run_id,
                RunErrorCategory.STORAGE_ERROR,
                _(
                    "The complete Research result exceeds the configured output-byte limit; Studio refuses it rather than truncating scientific arrays."
                ),
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
                "scientific_status": "RESEARCH",
                "dynamics_name": str(execution.result.dynamics_name),
                "boundary_name": str(execution.result.boundary_name),
                "spatial_shape": list(execution.result.spatial_shape),
                "n_time": int(execution.result.times.size),
                "solver_metadata": dict(execution.result.solver_metadata or {}),
                "derived_public_outputs": sorted(execution.derived),
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
                _("RESEARCH field Run %(number)s completed.") % {"number": locked.run_number},
            )
        logger.info(
            "analysis.research_field_run_completed run_id=%s duration_ms=%s lab_version=%s",
            run_id,
            round((time.monotonic() - started_clock) * 1000),
            run.agencitylab_version,
        )
        return "completed"
    except ResearchLabError as exc:
        if saved_path:
            analysis_storage().delete(saved_path)
        return _fail(run_id, exc.category, f"AgencityLab rejected this RESEARCH configuration: {exc}")
    except (OSError, ValueError, KeyError) as exc:
        if saved_path:
            try:
                analysis_storage().delete(saved_path)
            except OSError:
                logger.exception("analysis.research_result_cleanup_failed run_id=%s", run_id)
        return _fail(run_id, RunErrorCategory.SOURCE_ERROR, str(exc))
    except Exception:
        if saved_path:
            try:
                analysis_storage().delete(saved_path)
            except OSError:
                logger.exception("analysis.research_result_cleanup_failed run_id=%s", run_id)
        logger.exception("analysis.research_field_run_failed_unexpected run_id=%s", run_id)
        return _fail(
            run_id,
            RunErrorCategory.STUDIO_INTERNAL_ERROR,
            _("The RESEARCH field Run failed because of an internal Studio error."),
        )
