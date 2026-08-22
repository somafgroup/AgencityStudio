"""Server-rendered Project workflows with Workspace-inherited permissions."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from workspaces.permissions import (
    can_archive_project,
    can_create_project,
    can_delete_project,
    can_duplicate_project,
    can_edit_project,
    can_restore_project,
)
from workspaces.services import get_workspace_membership_or_404, workspace_memberships_for

from .forms import DeleteProjectForm, ProjectForm
from .models import Project
from .services import (
    archive_project,
    create_project,
    delete_project,
    duplicate_project,
    restore_project,
    update_project,
)

PROJECT_SECTIONS = {
    "datasets": (_("Datasets"), _("Datasets will be introduced by the Data Workspace plan.")),
    "systems": (_("Systems"), _("System definitions are not implemented in Plan 3.")),
    "analyses": (_("Analyses"), _("AgencityLab analysis workflows are not implemented in Plan 3.")),
    "comparisons": (_("Comparisons"), _("Scientific comparison workflows are not implemented yet.")),
    "reports": (_("Reports"), _("Reproducible report generation is a later development phase.")),
    "files": (_("Files"), _("Project file management is not implemented in Plan 3.")),
}


def _current_membership(request):
    memberships = list(workspace_memberships_for(request.user))
    preferred_slug = request.session.get("current_workspace_slug")
    current = next(
        (item for item in memberships if item.workspace.slug == preferred_slug),
        None,
    )
    if current is None:
        current = next((item for item in memberships if item.workspace.is_personal), None)
    if current is None and memberships:
        current = memberships[0]
    if current is not None:
        request.session["current_workspace_slug"] = current.workspace.slug
    return current


def _membership_and_project(request, workspace_slug: str, project_id, project_slug: str):
    membership = get_workspace_membership_or_404(user=request.user, slug=workspace_slug)
    try:
        project = Project.objects.select_related("workspace", "created_by").get(
            pk=project_id,
            workspace=membership.workspace,
            slug=project_slug,
        )
    except Project.DoesNotExist as exc:
        raise Http404 from exc
    request.session["current_workspace_slug"] = membership.workspace.slug
    return membership, project


def _project_context(membership, project: Project, *, active_section: str, **extra):
    return {
        "workspace": membership.workspace,
        "membership": membership,
        "project": project,
        "active_nav": "projects",
        "active_project_section": active_section,
        "page_title": project.name,
        "can_edit_project": can_edit_project(membership.user, project),
        "can_archive_project": can_archive_project(membership.user, project),
        "can_restore_project": can_restore_project(membership.user, project),
        "can_duplicate_project": can_duplicate_project(membership.user, project),
        "can_delete_project": can_delete_project(membership.user, project),
        **extra,
    }


@login_required
def project_list(request):
    membership = _current_membership(request)
    if membership is None:
        raise Http404

    projects = Project.objects.for_workspace(membership.workspace).select_related(
        "workspace", "created_by"
    )
    status_filter = request.GET.get("status", "active")
    projects = projects.archived() if status_filter == "archived" else projects.active()

    query = request.GET.get("q", "").strip()
    if query:
        projects = projects.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(domain__icontains=query)
        )

    sort = request.GET.get("sort", "updated")
    ordering = {
        "name": ("name",),
        "created": ("-created_at",),
        "updated": ("-updated_at",),
    }.get(sort, ("-updated_at",))
    projects = projects.order_by(*ordering)
    page_obj = Paginator(projects, 20).get_page(request.GET.get("page"))

    return render(
        request,
        "projects/list.html",
        {
            "active_nav": "projects",
            "page_title": _("Projects"),
            "workspace": membership.workspace,
            "membership": membership,
            "page_obj": page_obj,
            "query": query,
            "sort": sort,
            "status_filter": status_filter,
            "can_create_project": can_create_project(request.user, membership.workspace),
        },
    )


@login_required
def project_create(request, workspace_slug: str | None = None):
    if workspace_slug:
        membership = get_workspace_membership_or_404(user=request.user, slug=workspace_slug)
    else:
        membership = _current_membership(request)
        if membership is None:
            raise Http404
    if not can_create_project(request.user, membership.workspace):
        raise PermissionDenied

    request.session["current_workspace_slug"] = membership.workspace.slug
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = create_project(
            actor=request.user,
            workspace=membership.workspace,
            name=form.cleaned_data["name"],
            description=form.cleaned_data["description"],
            domain=form.cleaned_data["domain"],
            tags=form.cleaned_data["tags"],
            notes=form.cleaned_data["notes"],
        )
        messages.success(request, _("Project created."))
        return redirect(
            "projects:overview",
            workspace_slug=project.workspace.slug,
            project_id=project.pk,
            project_slug=project.slug,
        )
    return render(
        request,
        "projects/form.html",
        {
            "form": form,
            "workspace": membership.workspace,
            "active_nav": "projects",
            "page_title": _("New project"),
            "form_title": _("New project"),
            "submit_label": _("Create project"),
        },
    )


@login_required
def project_overview(request, workspace_slug: str, project_id, project_slug: str):
    membership, project = _membership_and_project(
        request, workspace_slug, project_id, project_slug
    )
    return render(
        request,
        "projects/overview.html",
        _project_context(membership, project, active_section="overview"),
    )


@login_required
def project_activity(request, workspace_slug: str, project_id, project_slug: str):
    membership, project = _membership_and_project(
        request, workspace_slug, project_id, project_slug
    )
    activity = project.activity.select_related("actor").all()
    return render(
        request,
        "projects/activity.html",
        _project_context(
            membership,
            project,
            active_section="activity",
            activity=activity,
        ),
    )


@login_required
def project_section(request, workspace_slug: str, project_id, project_slug: str, section: str):
    if section not in PROJECT_SECTIONS:
        raise Http404
    membership, project = _membership_and_project(
        request, workspace_slug, project_id, project_slug
    )
    title, description = PROJECT_SECTIONS[section]
    return render(
        request,
        "projects/section.html",
        _project_context(
            membership,
            project,
            active_section=section,
            section_title=title,
            section_description=description,
        ),
    )


@login_required
def project_settings(request, workspace_slug: str, project_id, project_slug: str):
    membership, project = _membership_and_project(
        request, workspace_slug, project_id, project_slug
    )
    if not can_edit_project(request.user, project):
        raise PermissionDenied
    form = ProjectForm(request.POST or None, instance=project)
    if request.method == "POST" and form.is_valid():
        try:
            project = update_project(
                actor=request.user,
                project=project,
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
                domain=form.cleaned_data["domain"],
                tags=form.cleaned_data["tags"],
                notes=form.cleaned_data["notes"],
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            messages.success(request, _("Project settings updated."))
            return redirect(
                "projects:settings",
                workspace_slug=project.workspace.slug,
                project_id=project.pk,
                project_slug=project.slug,
            )
    return render(
        request,
        "projects/settings.html",
        _project_context(
            membership,
            project,
            active_section="settings",
            form=form,
        ),
    )


@login_required
def project_duplicate(request, workspace_slug: str, project_id, project_slug: str):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    _, project = _membership_and_project(request, workspace_slug, project_id, project_slug)
    clone = duplicate_project(actor=request.user, project=project)
    messages.success(request, _("Project duplicated."))
    return redirect(
        "projects:overview",
        workspace_slug=clone.workspace.slug,
        project_id=clone.pk,
        project_slug=clone.slug,
    )


@login_required
def project_archive(request, workspace_slug: str, project_id, project_slug: str):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    _, project = _membership_and_project(request, workspace_slug, project_id, project_slug)
    archived = archive_project(actor=request.user, project=project)
    messages.success(request, _("Project archived."))
    return redirect(
        "projects:overview",
        workspace_slug=archived.workspace.slug,
        project_id=archived.pk,
        project_slug=archived.slug,
    )


@login_required
def project_restore(request, workspace_slug: str, project_id, project_slug: str):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    _, project = _membership_and_project(request, workspace_slug, project_id, project_slug)
    restored = restore_project(actor=request.user, project=project)
    messages.success(request, _("Project restored."))
    return redirect(
        "projects:overview",
        workspace_slug=restored.workspace.slug,
        project_id=restored.pk,
        project_slug=restored.slug,
    )


@login_required
def project_delete(request, workspace_slug: str, project_id, project_slug: str):
    membership, project = _membership_and_project(
        request, workspace_slug, project_id, project_slug
    )
    if not can_delete_project(request.user, project):
        raise PermissionDenied
    form = DeleteProjectForm(request.POST or None, project_name=project.name)
    if request.method == "POST" and form.is_valid():
        workspace = project.workspace
        delete_project(actor=request.user, project=project)
        messages.success(request, _("Project permanently deleted."))
        request.session["current_workspace_slug"] = workspace.slug
        return redirect("projects:list")
    return render(
        request,
        "projects/delete.html",
        _project_context(
            membership,
            project,
            active_section="settings",
            form=form,
        ),
    )
