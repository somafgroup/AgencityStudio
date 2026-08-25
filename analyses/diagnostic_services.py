"""Transactional lifecycle services for immutable scientific DiagnosticRuns."""

from __future__ import annotations

import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.http import Http404
from django.utils import timezone
from django.utils.translation import gettext as _

from labbridge.diagnostics import DIAGNOSTIC_PUBLIC_API, REQUIRED_CANONICAL_SERIES
from projects.models import ProjectActivity
from workspaces.permissions import can_run_diagnostics, can_view_diagnostic_run

from .diagnostic_results import DIAGNOSTIC_SCHEMA_VERSION
from .diagnostic_validation import normalize_diagnostic_configuration
from .models import (
    AnalysisResultArtifact,
    AnalysisRun,
    DiagnosticRun,
    RunStatus,
)
from .services import software_context
from .storage import analysis_storage


def _fingerprint(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _record(diagnostic_run: DiagnosticRun, *, event: str, detail: str) -> None:
    canonical = diagnostic_run.analysis_run
    ProjectActivity.objects.create(
        project=canonical.analysis.project,
        actor=diagnostic_run.created_by,
        event=event,
        detail=detail[:255],
    )


def _enqueue(diagnostic_run_id) -> None:
    from .diagnostic_tasks import execute_diagnostic_run

    execute_diagnostic_run.delay(str(diagnostic_run_id))


def _review_canonical_run(run: AnalysisRun) -> AnalysisResultArtifact:
    if run.status != RunStatus.COMPLETED:
        raise ValidationError(_("Diagnostics require a completed canonical AnalysisRun."))
    if not run.result_sha256:
        raise ValidationError(_("The canonical Run has no pinned result SHA-256."))
    try:
        artifact = run.result_artifact
    except AnalysisResultArtifact.DoesNotExist as exc:
        raise ValidationError(_("The canonical result artifact is unavailable.")) from exc
    if artifact.sha256 != run.result_sha256:
        raise ValidationError(_("The canonical result hash does not match its artifact provenance."))
    if not analysis_storage().exists(artifact.storage_path):
        raise ValidationError(_("The canonical result artifact is missing from private storage."))
    inventory = {str(item.get("name")) for item in artifact.manifest.get("series", [])}
    missing = [name for name in REQUIRED_CANONICAL_SERIES if name not in inventory]
    if missing:
        raise ValidationError(
            _("This historical result does not contain all public series required for diagnostics: %(series)s")
            % {"series": ", ".join(missing)}
        )
    return artifact


def diagnostic_review_snapshot(*, run: AnalysisRun, configuration: dict) -> dict:
    """Return the exact canonical/result and diagnostic contract shown at Review."""
    artifact = _review_canonical_run(run)
    normalized = normalize_diagnostic_configuration(configuration)
    context = software_context()
    if context["agencitylab_version"] != run.agencitylab_version:
        raise ValidationError(
            _("Diagnostics require the same AgencityLab version as the canonical Run."))
    if context["agencitylab_version"] != "1.1.3":
        raise ValidationError(_("AgencityLab 1.1.3 is required for the Plan 9 diagnostic contract."))
    return {
        "canonical_run": run,
        "canonical_artifact": artifact,
        "configuration": normalized,
        "api_identifiers": [DIAGNOSTIC_PUBLIC_API],
        "software": context,
    }


def _next_number(run: AnalysisRun) -> int:
    latest = DiagnosticRun.objects.filter(analysis_run=run).aggregate(value=Max("run_number"))[
        "value"
    ]
    return (latest or 0) + 1


@transaction.atomic
def queue_diagnostic_run(*, actor, run: AnalysisRun, configuration: dict) -> DiagnosticRun:
    """Pin one exact canonical result and queue a new immutable diagnostic execution."""
    locked = (
        AnalysisRun.objects.select_for_update()
        .select_related("analysis", "analysis__project", "analysis__project__workspace")
        .get(pk=run.pk)
    )
    if not can_run_diagnostics(actor, locked):
        raise PermissionDenied
    snapshot = diagnostic_review_snapshot(run=locked, configuration=configuration)
    context = snapshot["software"]
    normalized = snapshot["configuration"]
    payload = {
        "canonical_run_id": str(locked.pk),
        "canonical_result_sha256": locked.result_sha256,
        "diagnostic_api_identifiers": snapshot["api_identifiers"],
        "diagnostic_configuration": normalized,
        "agencitylab_version": context["agencitylab_version"],
        "diagnostic_schema_version": DIAGNOSTIC_SCHEMA_VERSION,
    }
    diagnostic_run = DiagnosticRun.objects.create(
        analysis_run=locked,
        run_number=_next_number(locked),
        status=RunStatus.QUEUED,
        canonical_result_sha256=locked.result_sha256,
        diagnostic_configuration=normalized,
        diagnostic_api_identifiers=snapshot["api_identifiers"],
        diagnostic_schema_version=DIAGNOSTIC_SCHEMA_VERSION,
        agencitylab_version=context["agencitylab_version"],
        studio_version=context["studio_version"],
        python_version=context["python_version"],
        execution_fingerprint=_fingerprint(payload),
        created_by=actor,
        queued_at=timezone.now(),
    )
    _record(
        diagnostic_run,
        event="DIAGNOSTIC_RUN_QUEUED",
        detail=_("Queued Diagnostic Run %(number)s for canonical Run %(canonical)s.")
        % {"number": diagnostic_run.run_number, "canonical": locked.run_number},
    )
    transaction.on_commit(lambda: _enqueue(diagnostic_run.pk))
    return diagnostic_run


@transaction.atomic
def rerun_diagnostic_run(*, actor, diagnostic_run: DiagnosticRun) -> DiagnosticRun:
    """Create a new DiagnosticRun from a historical immutable diagnostic configuration."""
    source = DiagnosticRun.objects.select_related(
        "analysis_run",
        "analysis_run__analysis",
        "analysis_run__analysis__project",
        "analysis_run__analysis__project__workspace",
    ).get(pk=diagnostic_run.pk)
    return queue_diagnostic_run(
        actor=actor,
        run=source.analysis_run,
        configuration=source.diagnostic_configuration,
    )


@transaction.atomic
def cancel_diagnostic_run(*, actor, diagnostic_run: DiagnosticRun) -> DiagnosticRun:
    locked = (
        DiagnosticRun.objects.select_for_update()
        .select_related("analysis_run", "analysis_run__analysis", "analysis_run__analysis__project")
        .get(pk=diagnostic_run.pk)
    )
    if not can_run_diagnostics(actor, locked.analysis_run):
        raise PermissionDenied
    if locked.status != RunStatus.QUEUED:
        raise ValidationError(_("Only queued DiagnosticRuns can be cancelled safely."))
    locked.status = RunStatus.CANCELLED
    locked.completed_at = timezone.now()
    locked.save(update_fields=("status", "completed_at"))
    return locked


def get_diagnostic_run_or_404(*, user, diagnostic_run_id) -> DiagnosticRun:
    try:
        diagnostic_run = DiagnosticRun.objects.select_related(
            "analysis_run",
            "analysis_run__analysis",
            "analysis_run__analysis__project",
            "analysis_run__analysis__project__workspace",
        ).get(pk=diagnostic_run_id)
    except (DiagnosticRun.DoesNotExist, ValueError) as exc:
        raise Http404 from exc
    if not can_view_diagnostic_run(user, diagnostic_run):
        raise Http404
    return diagnostic_run
