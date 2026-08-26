"""Server-rendered sensitivity workflow and private result endpoints."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from analyses.models import AnalysisRun, RunStatus
from analyses.services import get_analysis_or_404
from workspaces.permissions import can_run_analysis

from .forms import SensitivityStudyForm
from .models import SensitivityResultArtifact, StudyStatus
from .services import (
    cancel_sensitivity_study,
    get_sensitivity_study_or_404,
    queue_sensitivity_study,
    rerun_sensitivity_study,
    sensitivity_review_snapshot,
)
from .storage import read_sensitivity_result
from .visualization import available_metrics, chart_payload, manifest_payload, table_rows


def _run_or_404(user, analysis_id, run_id):
    analysis = get_analysis_or_404(user=user, analysis_id=analysis_id)
    try:
        run = AnalysisRun.objects.select_related(
            "analysis",
            "analysis__project",
            "analysis__project__workspace",
            "system_revision__system",
            "source_dataset_version",
            "source_prepared_artifact",
        ).get(pk=run_id, analysis=analysis)
    except AnalysisRun.DoesNotExist as exc:
        raise Http404 from exc
    return analysis, run


def _study_or_404(user, analysis_id, run_id, study_id):
    analysis, run = _run_or_404(user, analysis_id, run_id)
    study = get_sensitivity_study_or_404(user=user, study_id=study_id)
    if study.analysis_run_id != run.pk:
        raise Http404
    return analysis, run, study


def _context(request, analysis, run, **extra):
    return {
        "analysis": analysis,
        "run": run,
        "project": analysis.project,
        "workspace": analysis.project.workspace,
        "active_nav": "analyses",
        "active_project_section": "analyses",
        "can_run_sensitivity": run.status == RunStatus.COMPLETED
        and can_run_analysis(request.user, analysis),
        **extra,
    }


def _private_json(payload: dict) -> JsonResponse:
    response = JsonResponse(payload)
    response["Cache-Control"] = "private, no-store"
    response["Pragma"] = "no-cache"
    return response


def _stored(study):
    if study.status != StudyStatus.COMPLETED:
        raise Http404
    try:
        study.result_artifact
    except SensitivityResultArtifact.DoesNotExist as exc:
        raise Http404 from exc
    return read_sensitivity_result(study, verify_hash=True)


@login_required
def sensitivity_home(request, analysis_id, run_id):
    analysis, run = _run_or_404(request.user, analysis_id, run_id)
    studies = run.sensitivity_studies.select_related("result_artifact").all()
    return render(
        request,
        "sensitivity/home.html",
        _context(request, analysis, run, studies=studies, page_title=_("Sensitivity")),
    )


@login_required
def sensitivity_new(request, analysis_id, run_id):
    analysis, run = _run_or_404(request.user, analysis_id, run_id)
    if run.status != RunStatus.COMPLETED or not can_run_analysis(request.user, analysis):
        raise PermissionDenied
    grid_unit = str(run.parameter_snapshot.get("tau", {}).get("unit") or "")
    form = SensitivityStudyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        configuration = form.study_configuration(grid_unit=grid_unit)
        try:
            sensitivity_review_snapshot(run=run, configuration=configuration)
        except ValidationError as exc:
            form.add_error(None, str(exc))
        else:
            request.session[f"sensitivity_draft:{run.pk}"] = configuration
            return redirect("sensitivity:review", analysis_id=analysis.pk, run_id=run.pk)
    return render(
        request,
        "sensitivity/new.html",
        _context(
            request,
            analysis,
            run,
            form=form,
            grid_unit=grid_unit,
            page_title=_("New sensitivity study"),
        ),
    )


@login_required
def sensitivity_review(request, analysis_id, run_id):
    analysis, run = _run_or_404(request.user, analysis_id, run_id)
    if run.status != RunStatus.COMPLETED or not can_run_analysis(request.user, analysis):
        raise PermissionDenied
    key = f"sensitivity_draft:{run.pk}"
    configuration = request.session.get(key)
    if not isinstance(configuration, dict):
        messages.error(request, _("Configure a sensitivity study before Review."))
        return redirect("sensitivity:new", analysis_id=analysis.pk, run_id=run.pk)
    try:
        snapshot = sensitivity_review_snapshot(run=run, configuration=configuration)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("sensitivity:new", analysis_id=analysis.pk, run_id=run.pk)
    if request.method == "POST":
        study = queue_sensitivity_study(actor=request.user, run=run, configuration=configuration)
        request.session.pop(key, None)
        return redirect(
            "sensitivity:detail",
            analysis_id=analysis.pk,
            run_id=run.pk,
            study_id=study.pk,
        )
    return render(
        request,
        "sensitivity/review.html",
        _context(
            request,
            analysis,
            run,
            configuration=snapshot["configuration"],
            fixed=snapshot["fixed_parameter_snapshot"],
            public_api=snapshot["public_api_identifier"],
            page_title=_("Review sensitivity study"),
        ),
    )


@login_required
def sensitivity_detail(request, analysis_id, run_id, study_id):
    analysis, run, study = _study_or_404(request.user, analysis_id, run_id, study_id)
    stored = None
    metrics = ()
    rows = []
    result_error = ""
    if study.status == StudyStatus.COMPLETED:
        try:
            stored = _stored(study)
            metrics = available_metrics(study, stored)
            rows = table_rows(study, stored)
        except (OSError, ValueError) as exc:
            result_error = str(exc)
    return render(
        request,
        "sensitivity/detail.html",
        _context(
            request,
            analysis,
            run,
            study=study,
            stored=stored,
            metrics=metrics,
            rows=rows,
            result_error=result_error,
            page_title=_("Sensitivity study"),
        ),
    )


@login_required
def sensitivity_status(request, analysis_id, run_id, study_id):
    analysis, run, study = _study_or_404(request.user, analysis_id, run_id, study_id)
    return _private_json(
        {
            "study_id": str(study.pk),
            "status": study.status,
            "error_message": study.error_message,
            "completed": study.status == StudyStatus.COMPLETED,
        }
    )


@login_required
def sensitivity_cancel(request, analysis_id, run_id, study_id):
    analysis, run, study = _study_or_404(request.user, analysis_id, run_id, study_id)
    if request.method != "POST":
        raise Http404
    cancel_sensitivity_study(actor=request.user, study=study)
    return redirect("sensitivity:detail", analysis_id=analysis.pk, run_id=run.pk, study_id=study.pk)


@login_required
def sensitivity_rerun(request, analysis_id, run_id, study_id):
    analysis, run, study = _study_or_404(request.user, analysis_id, run_id, study_id)
    if request.method != "POST":
        raise Http404
    new_study = rerun_sensitivity_study(actor=request.user, study=study)
    return redirect(
        "sensitivity:detail",
        analysis_id=analysis.pk,
        run_id=run.pk,
        study_id=new_study.pk,
    )


@login_required
def sensitivity_manifest(request, analysis_id, run_id, study_id):
    _analysis, _run, study = _study_or_404(request.user, analysis_id, run_id, study_id)
    stored = _stored(study)
    return _private_json(manifest_payload(study, stored))


@login_required
def sensitivity_chart(request, analysis_id, run_id, study_id):
    _analysis, _run, study = _study_or_404(request.user, analysis_id, run_id, study_id)
    stored = _stored(study)
    metric = str(request.GET.get("metric") or "") or None
    return _private_json(chart_payload(study, stored, metric=metric))


@login_required
def sensitivity_table(request, analysis_id, run_id, study_id):
    _analysis, _run, study = _study_or_404(request.user, analysis_id, run_id, study_id)
    stored = _stored(study)
    return _private_json({"rows": table_rows(study, stored), "result_sha256": study.result_sha256})
