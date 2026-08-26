"""Server-rendered diagnostic workflow and private scientific data endpoints."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from workspaces.permissions import can_run_diagnostics

from .diagnostic_forms import DiagnosticConfigurationForm
from .diagnostic_registry import DEFERRED_OR_LEGACY, SUPPORTED_DIAGNOSTICS
from .diagnostic_services import (
    cancel_diagnostic_run,
    diagnostic_review_snapshot,
    get_diagnostic_run_or_404,
    queue_diagnostic_run,
    rerun_diagnostic_run,
)
from .diagnostic_storage import read_diagnostic_result
from .diagnostic_visualization import (
    diagnostic_manifest_payload,
    diagnostic_sample_payload,
    diagnostic_series_payload,
)
from .models import AnalysisRun, DiagnosticResultArtifact, DiagnosticRun, RunStatus
from .services import get_analysis_or_404
from .storage import analysis_storage, open_analysis_result_reader

DIAGNOSTIC_SECTIONS = {
    "overview",
    "coherence",
    "geometry",
    "events",
    "regimes",
    "real-agencity",
}


def _canonical_run_or_404(user, analysis_id, run_id):
    analysis = get_analysis_or_404(user=user, analysis_id=analysis_id)
    try:
        run = AnalysisRun.objects.select_related(
            "analysis",
            "analysis__project",
            "analysis__project__workspace",
            "system_revision__system",
        ).get(pk=run_id, analysis=analysis)
    except AnalysisRun.DoesNotExist as exc:
        raise Http404 from exc
    return analysis, run


def _diagnostic_for_run_or_404(user, analysis_id, run_id, diagnostic_run_id):
    analysis, canonical = _canonical_run_or_404(user, analysis_id, run_id)
    diagnostic = get_diagnostic_run_or_404(
        user=user, diagnostic_run_id=diagnostic_run_id
    )
    if diagnostic.analysis_run_id != canonical.pk:
        raise Http404
    return analysis, canonical, diagnostic


def _context(request, analysis, canonical, **extra):
    return {
        "analysis": analysis,
        "run": canonical,
        "project": analysis.project,
        "workspace": analysis.project.workspace,
        "active_nav": "analyses",
        "active_project_section": "analyses",
        "can_run_diagnostics": can_run_diagnostics(request.user, canonical),
        **extra,
    }


def _private_json(payload: dict, *, status: int = 200) -> JsonResponse:
    response = JsonResponse(payload, status=status)
    response["Cache-Control"] = "private, no-store"
    response["Pragma"] = "no-cache"
    return response


def _report_or_error(diagnostic: DiagnosticRun):
    if diagnostic.status != RunStatus.COMPLETED:
        raise Http404
    try:
        artifact = diagnostic.result_artifact
    except DiagnosticResultArtifact.DoesNotExist as exc:
        raise Http404 from exc
    stored = read_diagnostic_result(diagnostic, verify_hash=True)
    return artifact, stored.report


def _event_rows(report: dict) -> list[dict]:
    rows: list[dict] = []
    dynamic = report.get("events", {}).get("dynamic_peaks", {})
    for index, coordinate, value in zip(
        dynamic.get("indices", []),
        dynamic.get("times", []),
        dynamic.get("values", []),
        strict=False,
    ):
        rows.append(
            {
                "type": "D peak",
                "index": int(index),
                "coordinate": coordinate,
                "value": value,
                "status": dynamic.get("status", "diagnostic"),
            }
        )
    transitions = report.get("transitions", {})
    zeros = transitions.get("zeros", {})
    for index, coordinate in zip(
        zeros.get("indices", []), zeros.get("times", []), strict=False
    ):
        rows.append(
            {
                "type": "Canonical zero condition",
                "index": int(index),
                "coordinate": coordinate,
                "value": None,
                "status": zeros.get("status", "diagnostic"),
            }
        )
    critical = transitions.get("critical_surface_D_equals_S", {})
    for index, coordinate in zip(
        critical.get("indices", []), critical.get("times", []), strict=False
    ):
        rows.append(
            {
                "type": "D = S crossing",
                "index": int(index),
                "coordinate": coordinate,
                "value": None,
                "status": "DIAGNOSTIC / theory-facing transition",
            }
        )
    jumps = transitions.get("theta_jumps", {})
    for index, coordinate in zip(
        jumps.get("indices", []), jumps.get("times", []), strict=False
    ):
        rows.append(
            {
                "type": "Theta jump",
                "index": int(index),
                "coordinate": coordinate,
                "value": None,
                "status": jumps.get("status", "diagnostic"),
            }
        )
    return sorted(rows, key=lambda item: (item["index"], item["type"]))


@login_required
def diagnostics_home(request, analysis_id, run_id):
    analysis, canonical = _canonical_run_or_404(request.user, analysis_id, run_id)
    diagnostic_runs = canonical.diagnostic_runs.select_related("result_artifact").all()
    return render(
        request,
        "analyses/diagnostics_home.html",
        _context(
            request,
            analysis,
            canonical,
            diagnostic_runs=diagnostic_runs,
            supported=SUPPORTED_DIAGNOSTICS,
            deferred=DEFERRED_OR_LEGACY,
            page_title=_("Diagnostics"),
        ),
    )


@login_required
def diagnostic_new(request, analysis_id, run_id):
    analysis, canonical = _canonical_run_or_404(request.user, analysis_id, run_id)
    if not can_run_diagnostics(request.user, canonical):
        raise PermissionDenied
    if canonical.status != RunStatus.COMPLETED:
        raise ValidationError(_("Diagnostics require a completed canonical Run."))
    form = DiagnosticConfigurationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        configuration = form.diagnostic_configuration()
        try:
            diagnostic_review_snapshot(run=canonical, configuration=configuration)
        except ValidationError as exc:
            form.add_error(None, str(exc))
        else:
            request.session[f"diagnostic_draft:{canonical.pk}"] = configuration
            return redirect(
                "analysis:diagnostic-review",
                analysis_id=analysis.pk,
                run_id=canonical.pk,
            )
    return render(
        request,
        "analyses/diagnostic_new.html",
        _context(
            request,
            analysis,
            canonical,
            form=form,
            supported=SUPPORTED_DIAGNOSTICS,
            page_title=_("New Diagnostic Run"),
        ),
    )


@login_required
def diagnostic_review(request, analysis_id, run_id):
    analysis, canonical = _canonical_run_or_404(request.user, analysis_id, run_id)
    if not can_run_diagnostics(request.user, canonical):
        raise PermissionDenied
    key = f"diagnostic_draft:{canonical.pk}"
    configuration = request.session.get(key)
    if not isinstance(configuration, dict):
        messages.error(request, _("Configure diagnostics before Review."))
        return redirect(
            "analysis:diagnostic-new", analysis_id=analysis.pk, run_id=canonical.pk
        )
    try:
        snapshot = diagnostic_review_snapshot(
            run=canonical, configuration=configuration
        )
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect(
            "analysis:diagnostic-new", analysis_id=analysis.pk, run_id=canonical.pk
        )
    if request.method == "POST":
        diagnostic = queue_diagnostic_run(
            actor=request.user,
            run=canonical,
            configuration=snapshot["configuration"],
        )
        request.session.pop(key, None)
        return redirect(
            "analysis:diagnostic-detail",
            analysis_id=analysis.pk,
            run_id=canonical.pk,
            diagnostic_run_id=diagnostic.pk,
        )
    return render(
        request,
        "analyses/diagnostic_review.html",
        _context(
            request,
            analysis,
            canonical,
            snapshot=snapshot,
            supported=SUPPORTED_DIAGNOSTICS,
            page_title=_("Review Diagnostic Run"),
        ),
    )


@login_required
def diagnostic_detail(request, analysis_id, run_id, diagnostic_run_id):
    analysis, canonical, diagnostic = _diagnostic_for_run_or_404(
        request.user, analysis_id, run_id, diagnostic_run_id
    )
    artifact = None
    artifact_available = False
    report = None
    if diagnostic.status == RunStatus.COMPLETED:
        artifact = DiagnosticResultArtifact.objects.filter(
            diagnostic_run=diagnostic
        ).first()
        if artifact is not None:
            artifact_available = analysis_storage().exists(artifact.storage_path)
            if artifact_available:
                try:
                    report = read_diagnostic_result(diagnostic).report
                except (OSError, ValueError):
                    artifact_available = False
    return render(
        request,
        "analyses/diagnostic_detail.html",
        _context(
            request,
            analysis,
            canonical,
            diagnostic=diagnostic,
            artifact=artifact,
            artifact_available=artifact_available,
            report=report,
            page_title=_("Diagnostic Run"),
        ),
    )


@login_required
def diagnostic_status(request, analysis_id, run_id, diagnostic_run_id):
    _analysis, _canonical, diagnostic = _diagnostic_for_run_or_404(
        request.user, analysis_id, run_id, diagnostic_run_id
    )
    response = HttpResponse(
        f'<span class="badge">{diagnostic.get_status_display().upper()}</span>',
        content_type="text/html",
    )
    if diagnostic.status in {RunStatus.QUEUED, RunStatus.RUNNING}:
        response["HX-Refresh"] = "false"
    return response


@login_required
def diagnostic_cancel(request, analysis_id, run_id, diagnostic_run_id):
    analysis, canonical, diagnostic = _diagnostic_for_run_or_404(
        request.user, analysis_id, run_id, diagnostic_run_id
    )
    if request.method != "POST":
        raise Http404
    try:
        cancel_diagnostic_run(actor=request.user, diagnostic_run=diagnostic)
    except ValidationError as exc:
        messages.error(request, str(exc))
    return redirect(
        "analysis:diagnostic-detail",
        analysis_id=analysis.pk,
        run_id=canonical.pk,
        diagnostic_run_id=diagnostic.pk,
    )


@login_required
def diagnostic_rerun(request, analysis_id, run_id, diagnostic_run_id):
    analysis, canonical, diagnostic = _diagnostic_for_run_or_404(
        request.user, analysis_id, run_id, diagnostic_run_id
    )
    if request.method != "POST":
        raise Http404
    new_run = rerun_diagnostic_run(actor=request.user, diagnostic_run=diagnostic)
    return redirect(
        "analysis:diagnostic-detail",
        analysis_id=analysis.pk,
        run_id=canonical.pk,
        diagnostic_run_id=new_run.pk,
    )


@login_required
def diagnostic_workspace(
    request, analysis_id, run_id, diagnostic_run_id, section="overview"
):
    if section not in DIAGNOSTIC_SECTIONS:
        raise Http404
    analysis, canonical, diagnostic = _diagnostic_for_run_or_404(
        request.user, analysis_id, run_id, diagnostic_run_id
    )
    try:
        artifact, report = _report_or_error(diagnostic)
    except (OSError, ValueError):
        return render(
            request,
            "analyses/diagnostic_unavailable.html",
            _context(
                request,
                analysis,
                canonical,
                diagnostic=diagnostic,
                page_title=_("Diagnostic result unavailable"),
            ),
            status=409,
        )
    sample = request.GET.get("sample", "0")
    try:
        selected_sample = max(0, int(sample))
    except ValueError:
        selected_sample = 0
    return render(
        request,
        "analyses/diagnostic_workspace.html",
        _context(
            request,
            analysis,
            canonical,
            diagnostic=diagnostic,
            artifact=artifact,
            report=report,
            section=section,
            selected_sample=selected_sample,
            event_rows=_event_rows(report),
            plateaus=report.get("structural_plateaus", {}),
            supported=SUPPORTED_DIAGNOSTICS,
            page_title=_("Diagnostic Workspace"),
        ),
    )


@login_required
def diagnostic_manifest(request, analysis_id, run_id, diagnostic_run_id):
    _analysis, canonical, diagnostic = _diagnostic_for_run_or_404(
        request.user, analysis_id, run_id, diagnostic_run_id
    )
    try:
        artifact, report = _report_or_error(diagnostic)
        with open_analysis_result_reader(canonical) as reader:
            payload = diagnostic_manifest_payload(
                reader,
                report=report,
                diagnostic_result_sha256=artifact.sha256,
                canonical_result_sha256=canonical.result_sha256,
                diagnostic_run=diagnostic,
            )
        return _private_json(payload)
    except (OSError, ValueError, KeyError):
        return _private_json({"error": _("Unable to load this diagnostic result.")}, status=409)


@login_required
def diagnostic_series(request, analysis_id, run_id, diagnostic_run_id):
    _analysis, canonical, diagnostic = _diagnostic_for_run_or_404(
        request.user, analysis_id, run_id, diagnostic_run_id
    )
    names = tuple(
        value.strip()
        for value in request.GET.get("series", "").split(",")
        if value.strip()
    )
    try:
        start = int(request.GET.get("start", "0"))
        stop_raw = request.GET.get("stop")
        stop = int(stop_raw) if stop_raw not in (None, "") else None
        max_points = min(max(int(request.GET.get("max_points", "5000")), 1), 20000)
        artifact, report = _report_or_error(diagnostic)
        with open_analysis_result_reader(canonical) as reader:
            payload = diagnostic_series_payload(
                reader,
                report=report,
                names=names,
                start=start,
                stop=stop,
                max_points=max_points,
                diagnostic_result_sha256=artifact.sha256,
            )
        return _private_json(payload)
    except (OSError, ValueError, KeyError, IndexError):
        return _private_json({"error": _("Unable to load this diagnostic visualization.")}, status=400)


@login_required
def diagnostic_sample(request, analysis_id, run_id, diagnostic_run_id):
    _analysis, canonical, diagnostic = _diagnostic_for_run_or_404(
        request.user, analysis_id, run_id, diagnostic_run_id
    )
    try:
        index = int(request.GET.get("index", "0"))
        artifact, report = _report_or_error(diagnostic)
        with open_analysis_result_reader(canonical) as reader:
            payload = diagnostic_sample_payload(
                reader,
                report=report,
                index=index,
                diagnostic_result_sha256=artifact.sha256,
            )
        return _private_json(payload)
    except (OSError, ValueError, KeyError, IndexError):
        return _private_json({"error": _("Unable to load this diagnostic sample.")}, status=400)
