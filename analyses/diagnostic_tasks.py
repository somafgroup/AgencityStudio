"""Celery execution for immutable AgencityLab DiagnosticRuns."""

from __future__ import annotations

import logging
import time
import uuid

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from labbridge.diagnostics import DiagnosticLabError, execute_diagnostics
from projects.models import ProjectActivity

from .diagnostic_storage import write_diagnostic_result
from .models import (
    DiagnosticErrorCategory,
    DiagnosticResultArtifact,
    DiagnosticRun,
    RunStatus,
)
from .storage import analysis_storage, read_analysis_result

logger = logging.getLogger(__name__)


def _locked(diagnostic_run_id) -> DiagnosticRun:
    return (
        DiagnosticRun.objects.select_for_update()
        .select_related(
            "analysis_run",
            "analysis_run__analysis",
            "analysis_run__analysis__project",
        )
        .get(pk=diagnostic_run_id)
    )


def _record(run: DiagnosticRun, event: str, detail: str) -> None:
    ProjectActivity.objects.create(
        project=run.analysis_run.analysis.project,
        actor=run.created_by,
        event=event,
        detail=detail[:255],
    )


def _fail(diagnostic_run_id, category: str, message: str) -> str:
    with transaction.atomic():
        try:
            run = _locked(diagnostic_run_id)
        except DiagnosticRun.DoesNotExist:
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
            "DIAGNOSTIC_RUN_FAILED",
            _("Diagnostic Run %(number)s failed.") % {"number": run.run_number},
        )
    return "failed"


@shared_task(name="analyses.execute_diagnostic_run")
def execute_diagnostic_run(diagnostic_run_id: str) -> str:
    """Execute one diagnostic configuration once against its pinned canonical artifact."""
    started_clock = time.monotonic()
    with transaction.atomic():
        try:
            run = _locked(diagnostic_run_id)
        except DiagnosticRun.DoesNotExist:
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
        "diagnostic.run_started diagnostic_run_id=%s canonical_run_id=%s lab_version=%s",
        diagnostic_run_id,
        run.analysis_run_id,
        run.agencitylab_version,
    )
    saved_path = None
    try:
        canonical = run.analysis_run
        if canonical.result_sha256 != run.canonical_result_sha256:
            return _fail(
                diagnostic_run_id,
                DiagnosticErrorCategory.RESULT_INPUT_ERROR,
                _("The canonical result fingerprint no longer matches the DiagnosticRun provenance."),
            )
        stored = read_analysis_result(canonical, verify_hash=True)
        execution = execute_diagnostics(
            arrays=stored.arrays,
            manifest=stored.manifest,
            configuration=run.diagnostic_configuration,
        )
        artifact_id = uuid.uuid4()
        saved_path, serialized = write_diagnostic_result(
            report=execution.report,
            diagnostic_run=run,
            artifact_id=artifact_id,
        )
        with transaction.atomic():
            locked = _locked(diagnostic_run_id)
            if locked.status != RunStatus.RUNNING:
                analysis_storage().delete(saved_path)
                return "stale-result"
            if locked.canonical_result_sha256 != locked.analysis_run.result_sha256:
                analysis_storage().delete(saved_path)
                return _fail(
                    diagnostic_run_id,
                    DiagnosticErrorCategory.RESULT_INPUT_ERROR,
                    _("The canonical result changed while diagnostics were running."),
                )
            DiagnosticResultArtifact.objects.create(
                id=artifact_id,
                diagnostic_run=locked,
                storage_path=saved_path,
                format=serialized.manifest["format"],
                schema_version=serialized.manifest["schema_version"],
                sha256=serialized.sha256,
                size_bytes=serialized.size_bytes,
                manifest=serialized.manifest,
            )
            locked.status = RunStatus.COMPLETED
            locked.result_sha256 = serialized.sha256
            locked.warnings = [*locked.warnings, *execution.warnings]
            locked.completed_at = timezone.now()
            locked.save(
                update_fields=("status", "result_sha256", "warnings", "completed_at")
            )
            _record(
                locked,
                "DIAGNOSTIC_RUN_COMPLETED",
                _("Diagnostic Run %(number)s completed.") % {"number": locked.run_number},
            )
        logger.info(
            "diagnostic.run_completed diagnostic_run_id=%s canonical_run_id=%s duration_ms=%s lab_version=%s",
            diagnostic_run_id,
            run.analysis_run_id,
            round((time.monotonic() - started_clock) * 1000),
            run.agencitylab_version,
        )
        return "completed"
    except DiagnosticLabError as exc:
        if saved_path:
            analysis_storage().delete(saved_path)
        logger.warning(
            "diagnostic.run_lab_failed diagnostic_run_id=%s category=%s",
            diagnostic_run_id,
            exc.category,
        )
        return _fail(
            diagnostic_run_id,
            exc.category,
            _("AgencityLab rejected this diagnostic configuration: %(message)s")
            % {"message": str(exc)},
        )
    except OSError:
        if saved_path:
            try:
                analysis_storage().delete(saved_path)
            except OSError:
                logger.exception(
                    "diagnostic.result_cleanup_failed diagnostic_run_id=%s",
                    diagnostic_run_id,
                )
        logger.exception("diagnostic.run_storage_failed diagnostic_run_id=%s", diagnostic_run_id)
        return _fail(
            diagnostic_run_id,
            DiagnosticErrorCategory.STORAGE_ERROR,
            _("The diagnostic result could not be stored safely."),
        )
    except Exception:
        if saved_path:
            try:
                analysis_storage().delete(saved_path)
            except OSError:
                logger.exception(
                    "diagnostic.result_cleanup_failed diagnostic_run_id=%s",
                    diagnostic_run_id,
                )
        logger.exception("diagnostic.run_failed_unexpected diagnostic_run_id=%s", diagnostic_run_id)
        return _fail(
            diagnostic_run_id,
            DiagnosticErrorCategory.STUDIO_INTERNAL_ERROR,
            _("The DiagnosticRun failed because of an internal Studio error."),
        )
