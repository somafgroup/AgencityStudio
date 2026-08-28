"""Server-rendered builder and immutable Run views for multivariate Analyses."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from workspaces.permissions import can_create_analysis, can_edit_analysis, can_run_analysis

from .forms import AnalysisStartForm
from .models import AnalysisKind
from .multivariate_creation import create_multivariate_analysis
from .multivariate_forms import MultivariateConfigurationForm
from .multivariate_services import (
    configure_multivariate_analysis,
    queue_multivariate_run,
    rerun_multivariate_run,
    review_multivariate_snapshot,
)
from .sources import SourceContractError
from .views import _analysis_context, _membership_project, _run_or_404, get_analysis_or_404


def _multivariate_or_404(user, analysis_id):
    analysis = get_analysis_or_404(user=user, analysis_id=analysis_id)
    if analysis.analysis_kind != AnalysisKind.MULTIVARIATE:
        raise Http404
    return analysis


@login_required
def multivariate_create(request, workspace_slug, project_id, project_slug):
    _membership, project = _membership_project(
        request,
        workspace_slug,
        project_id,
        project_slug,
    )
    if not can_create_analysis(request.user, project):
        raise PermissionDenied
    form = AnalysisStartForm(request.POST or None, project=project)
    if request.method == "POST" and form.is_valid():
        source_type, source_id = form.cleaned_data["source"]
        try:
            analysis = create_multivariate_analysis(
                actor=request.user,
                project=project,
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
                source_type=source_type,
                source_id=source_id,
            )
        except (ValidationError, SourceContractError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("analysis:multivariate-configure", analysis_id=analysis.pk)
    return render(
        request,
        "analyses/multivariate_start.html",
        {
            "form": form,
            "project": project,
            "workspace": project.workspace,
            "active_nav": "projects",
            "active_project_section": "analyses",
            "page_title": _("New Multivariate Analysis"),
        },
    )


@login_required
def multivariate_configure(request, analysis_id):
    analysis = _multivariate_or_404(request.user, analysis_id)
    if not can_edit_analysis(request.user, analysis):
        raise PermissionDenied
    try:
        form = MultivariateConfigurationForm(
            request.POST or None,
            analysis=analysis,
        )
    except SourceContractError as exc:
        messages.error(request, str(exc))
        return redirect("analysis:detail", analysis_id=analysis.pk)
    if request.method == "POST" and form.is_valid():
        try:
            configure_multivariate_analysis(
                actor=request.user,
                analysis=analysis,
                coordinate_position=int(form.cleaned_data["coordinate_position"]),
                system_revision=form.cleaned_data["system_revision"],
                component_configs=form.component_configs(),
                parameter_modes=form.parameter_modes(),
            )
        except (ValidationError, SourceContractError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("analysis:multivariate-review", analysis_id=analysis.pk)
    return render(
        request,
        "analyses/multivariate_configure.html",
        _analysis_context(request, analysis, form=form),
    )


@login_required
def multivariate_review(request, analysis_id):
    analysis = _multivariate_or_404(request.user, analysis_id)
    try:
        snapshot = review_multivariate_snapshot(analysis)
    except (KeyError, TypeError, ValueError, ValidationError, SourceContractError):
        messages.error(
            request,
            _("Complete the Multivariate Analysis configuration before Review."),
        )
        return redirect("analysis:multivariate-configure", analysis_id=analysis.pk)
    if request.method == "POST":
        if not can_run_analysis(request.user, analysis):
            raise PermissionDenied
        try:
            run = queue_multivariate_run(actor=request.user, analysis=analysis)
        except (ValidationError, SourceContractError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            return redirect(
                "analysis:run-detail",
                analysis_id=analysis.pk,
                run_id=run.pk,
            )
    return render(
        request,
        "analyses/multivariate_review.html",
        _analysis_context(request, analysis, snapshot=snapshot),
    )


@login_required
def multivariate_rerun(request, analysis_id, run_id):
    analysis, run = _run_or_404(request.user, analysis_id, run_id)
    if analysis.analysis_kind != AnalysisKind.MULTIVARIATE:
        raise Http404
    if request.method != "POST":
        raise Http404
    try:
        new_run = rerun_multivariate_run(actor=request.user, run=run)
    except (ValidationError, SourceContractError) as exc:
        messages.error(request, str(exc))
        return redirect("analysis:run-detail", analysis_id=analysis.pk, run_id=run.pk)
    return redirect(
        "analysis:run-detail",
        analysis_id=analysis.pk,
        run_id=new_run.pk,
    )
