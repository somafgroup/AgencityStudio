"""Server-rendered canonical Analysis configuration, execution and provenance views."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from projects.models import Project
from workspaces.permissions import (
    can_archive_analysis,
    can_create_analysis,
    can_delete_analysis,
    can_edit_analysis,
    can_restore_analysis,
    can_run_analysis,
)
from workspaces.services import get_workspace_membership_or_404, workspace_memberships_for

from .forms import AnalysisConfigurationForm, AnalysisStartForm
from .models import Analysis, AnalysisRun, RunStatus
from .services import (
    archive_analysis,
    cancel_analysis_run,
    configure_analysis,
    create_analysis,
    delete_analysis,
    get_analysis_or_404,
    queue_analysis_run,
    restore_analysis,
    review_snapshot,
)
from .sources import SourceContractError
from .storage import analysis_storage


def _current_membership(request):
    memberships = list(workspace_memberships_for(request.user))
    slug = request.session.get("current_workspace_slug")
    membership = next((item for item in memberships if item.workspace.slug == slug), None)
    if membership is None:
        membership = next((item for item in memberships if item.workspace.is_personal), None)
    if membership is None and memberships:
        membership = memberships[0]
    if membership:
        request.session["current_workspace_slug"] = membership.workspace.slug
    return membership


def _membership_project(request, workspace_slug, project_id, project_slug):
    membership = get_workspace_membership_or_404(user=request.user, slug=workspace_slug)
    try:
        project = Project.objects.select_related("workspace").get(
            pk=project_id, workspace=membership.workspace, slug=project_slug
        )
    except Project.DoesNotExist as exc:
        raise Http404 from exc
    request.session["current_workspace_slug"] = membership.workspace.slug
    return membership, project


def _analysis_context(request, analysis, **extra):
    return {
        "analysis": analysis,
        "project": analysis.project,
        "workspace": analysis.project.workspace,
        "active_nav": "analyses",
        "active_project_section": "analyses",
        "page_title": analysis.name,
        "can_edit_analysis": can_edit_analysis(request.user, analysis),
        "can_run_analysis": can_run_analysis(request.user, analysis),
        "can_archive_analysis": can_archive_analysis(request.user, analysis),
        "can_restore_analysis": can_restore_analysis(request.user, analysis),
        "can_delete_analysis": can_delete_analysis(request.user, analysis),
        **extra,
    }


@login_required
def global_analysis_list(request):
    membership = _current_membership(request)
    analyses = Analysis.objects.none()
    if membership:
        analyses = (
            Analysis.objects.for_workspace(membership.workspace)
            .select_related("project", "created_by")
            .prefetch_related("runs")
        )
    return render(
        request,
        "analyses/list.html",
        {
            "analyses": analyses,
            "workspace": membership.workspace if membership else None,
            "project": None,
            "active_nav": "analyses",
            "page_title": _("Analyses"),
        },
    )


@login_required
def project_analysis_list(request, workspace_slug, project_id, project_slug):
    membership, project = _membership_project(request, workspace_slug, project_id, project_slug)
    analyses = Analysis.objects.for_project(project).select_related("created_by").prefetch_related("runs")
    return render(
        request,
        "analyses/list.html",
        {
            "analyses": analyses,
            "workspace": membership.workspace,
            "project": project,
            "can_create_analysis": can_create_analysis(request.user, project),
            "active_nav": "projects",
            "active_project_section": "analyses",
            "page_title": _("Analyses"),
        },
    )


@login_required
def analysis_create(request, workspace_slug, project_id, project_slug):
    _membership, project = _membership_project(request, workspace_slug, project_id, project_slug)
    if not can_create_analysis(request.user, project):
        raise PermissionDenied
    form = AnalysisStartForm(request.POST or None, project=project)
    if request.method == "POST" and form.is_valid():
        source_type, source_id = form.cleaned_data["source"]
        try:
            analysis = create_analysis(
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
            return redirect("analysis:configure", analysis_id=analysis.pk)
    return render(
        request,
        "analyses/start.html",
        {"form": form, "project": project, "workspace": project.workspace, "active_nav": "projects", "active_project_section": "analyses", "page_title": _("New Analysis")},
    )


@login_required
def analysis_configure(request, analysis_id):
    analysis = get_analysis_or_404(user=request.user, analysis_id=analysis_id)
    if not can_edit_analysis(request.user, analysis):
        raise PermissionDenied
    try:
        form = AnalysisConfigurationForm(request.POST or None, analysis=analysis)
    except SourceContractError as exc:
        messages.error(request, str(exc))
        return redirect("analysis:detail", analysis_id=analysis.pk)
    if request.method == "POST" and form.is_valid():
        options = {key: form.cleaned_data[key] for key in ("domain", "mechanism", "system_type", "environment", "geometry")}
        try:
            configure_analysis(
                actor=request.user,
                analysis=analysis,
                coordinate_position=int(form.cleaned_data["coordinate_position"]),
                observable_position=int(form.cleaned_data["observable_position"]),
                system_revision=form.cleaned_data["system_revision"],
                system_observable=form.cleaned_data["system_observable"],
                options=options,
            )
        except (ValidationError, SourceContractError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("analysis:review", analysis_id=analysis.pk)
    return render(request, "analyses/configure.html", _analysis_context(request, analysis, form=form))


@login_required
def analysis_review(request, analysis_id):
    analysis = get_analysis_or_404(user=request.user, analysis_id=analysis_id)
    try:
        snapshot = review_snapshot(analysis)
    except (KeyError, ValueError, ValidationError, SourceContractError):
        messages.error(request, _("Complete the Analysis configuration before Review."))
        return redirect("analysis:configure", analysis_id=analysis.pk)
    if request.method == "POST":
        if not can_run_analysis(request.user, analysis):
            raise PermissionDenied
        try:
            run = queue_analysis_run(actor=request.user, analysis=analysis)
        except (ValidationError, SourceContractError) as exc:
            messages.error(request, str(exc))
        else:
            return redirect("analysis:run-detail", analysis_id=analysis.pk, run_id=run.pk)
    return render(request, "analyses/review.html", _analysis_context(request, analysis, snapshot=snapshot))


@login_required
def analysis_detail(request, analysis_id):
    analysis = get_analysis_or_404(user=request.user, analysis_id=analysis_id)
    runs = analysis.runs.select_related("source_dataset_version__dataset", "source_prepared_artifact__preparation", "system_revision__system").order_by("-run_number")
    return render(request, "analyses/detail.html", _analysis_context(request, analysis, runs=runs))


def _run_or_404(user, analysis_id, run_id):
    analysis = get_analysis_or_404(user=user, analysis_id=analysis_id)
    try:
        run = AnalysisRun.objects.select_related(
            "analysis", "analysis__project", "analysis__project__workspace", "system_revision__system", "system_observable",
            "source_dataset_version__dataset", "source_prepared_artifact__preparation",
        ).get(pk=run_id, analysis=analysis)
    except AnalysisRun.DoesNotExist as exc:
        raise Http404 from exc
    return analysis, run


@login_required
def run_detail(request, analysis_id, run_id):
    analysis, run = _run_or_404(request.user, analysis_id, run_id)
    artifact = None
    artifact_available = False
    if run.status == RunStatus.COMPLETED:
        try:
            artifact = run.result_artifact
            artifact_available = analysis_storage().exists(artifact.storage_path)
        except Exception:
            artifact_available = False
    return render(
        request,
        "analyses/run_detail.html",
        _analysis_context(request, analysis, run=run, artifact=artifact, artifact_available=artifact_available),
    )


@login_required
def run_status(request, analysis_id, run_id):
    _analysis, run = _run_or_404(request.user, analysis_id, run_id)
    response = HttpResponse(
        f'<span class="badge">{run.get_status_display()}</span>',
        content_type="text/html",
    )
    if run.status in {RunStatus.QUEUED, RunStatus.RUNNING}:
        response["HX-Refresh"] = "false"
    return response


@login_required
def run_cancel(request, analysis_id, run_id):
    analysis, run = _run_or_404(request.user, analysis_id, run_id)
    if request.method != "POST":
        raise Http404
    try:
        cancel_analysis_run(actor=request.user, run=run)
    except ValidationError as exc:
        messages.error(request, str(exc))
    return redirect("analysis:run-detail", analysis_id=analysis.pk, run_id=run.pk)


@login_required
def analysis_archive(request, analysis_id):
    analysis = get_analysis_or_404(user=request.user, analysis_id=analysis_id)
    if request.method != "POST":
        raise Http404
    archive_analysis(actor=request.user, analysis=analysis)
    return redirect("analysis:detail", analysis_id=analysis.pk)


@login_required
def analysis_restore(request, analysis_id):
    analysis = get_analysis_or_404(user=request.user, analysis_id=analysis_id)
    if request.method != "POST":
        raise Http404
    restore_analysis(actor=request.user, analysis=analysis)
    return redirect("analysis:detail", analysis_id=analysis.pk)


@login_required
def analysis_delete(request, analysis_id):
    analysis = get_analysis_or_404(user=request.user, analysis_id=analysis_id)
    if request.method != "POST":
        raise Http404
    project = analysis.project
    delete_analysis(actor=request.user, analysis=analysis)
    messages.success(request, _("Analysis deleted."))
    return redirect("analysis:project-list", workspace_slug=project.workspace.slug, project_id=project.pk, project_slug=project.slug)
