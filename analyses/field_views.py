"""Server-rendered EXPERIMENTAL observable spatial field workflow."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from datasets.field_source import FieldSourceError
from workspaces.permissions import can_create_analysis, can_edit_analysis, can_run_analysis

from .field_creation import create_observable_field_analysis
from .field_forms import FieldAnalysisStartForm, FieldConfigurationForm
from .field_services import (
    configure_observable_field_analysis,
    observable_field_review_snapshot,
    queue_observable_field_run,
    rerun_observable_field,
)
from .services import get_analysis_or_404
from .views import _analysis_context, _membership_project, _run_or_404


@login_required
def observable_field_create(request, workspace_slug, project_id, project_slug):
    _membership, project = _membership_project(request, workspace_slug, project_id, project_slug)
    if not can_create_analysis(request.user, project):
        raise PermissionDenied
    form = FieldAnalysisStartForm(request.POST or None, project=project)
    if request.method == "POST" and form.is_valid():
        try:
            analysis = create_observable_field_analysis(
                actor=request.user,
                project=project,
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
                source=form.cleaned_data["source"],
            )
        except ValidationError as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("analysis:field-configure", analysis_id=analysis.pk)
    return render(
        request,
        "analyses/field_start.html",
        {
            "form": form,
            "project": project,
            "workspace": project.workspace,
            "active_nav": "projects",
            "active_project_section": "analyses",
            "page_title": _("New Observable Spatial Field Analysis"),
        },
    )


@login_required
def observable_field_configure(request, analysis_id):
    analysis = get_analysis_or_404(user=request.user, analysis_id=analysis_id)
    if not can_edit_analysis(request.user, analysis):
        raise PermissionDenied
    try:
        form = FieldConfigurationForm(request.POST or None, analysis=analysis)
    except (FieldSourceError, ValidationError) as exc:
        messages.error(request, str(exc))
        return redirect("analysis:detail", analysis_id=analysis.pk)
    if request.method == "POST" and form.is_valid():
        try:
            configure_observable_field_analysis(
                actor=request.user, analysis=analysis, values=form.cleaned_data
            )
        except (FieldSourceError, ValidationError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("analysis:field-review", analysis_id=analysis.pk)
    source = analysis.draft_configuration.get("source_id")
    return render(
        request,
        "analyses/field_configure.html",
        _analysis_context(request, analysis, form=form, source_id=source),
    )


@login_required
def observable_field_review(request, analysis_id):
    analysis = get_analysis_or_404(user=request.user, analysis_id=analysis_id)
    try:
        snapshot = observable_field_review_snapshot(analysis)
    except (FieldSourceError, ValidationError, KeyError, ValueError) as exc:
        messages.error(request, str(exc))
        return redirect("analysis:field-configure", analysis_id=analysis.pk)
    if request.method == "POST":
        if not can_run_analysis(request.user, analysis):
            raise PermissionDenied
        try:
            run = queue_observable_field_run(actor=request.user, analysis=analysis)
        except (FieldSourceError, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            return redirect("analysis:run-detail", analysis_id=analysis.pk, run_id=run.pk)
    return render(
        request,
        "analyses/field_review.html",
        _analysis_context(request, analysis, snapshot=snapshot),
    )


@login_required
def observable_field_rerun(request, analysis_id, run_id):
    analysis, run = _run_or_404(request.user, analysis_id, run_id)
    if request.method != "POST":
        raise Http404
    try:
        new_run = rerun_observable_field(actor=request.user, run=run)
    except (FieldSourceError, ValidationError) as exc:
        messages.error(request, str(exc))
        return redirect("analysis:run-detail", analysis_id=analysis.pk, run_id=run.pk)
    return redirect("analysis:run-detail", analysis_id=analysis.pk, run_id=new_run.pk)
