"""Views for the application shell and operational health surfaces."""

import redis
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.db.utils import DatabaseError
from django.http import Http404, JsonResponse
from django.shortcuts import render

from datasets.models import Dataset
from labbridge.service import get_lab_version, lab_is_compatible
from projects.models import Project
from workspaces.permissions import can_create_project
from workspaces.services import workspace_memberships_for

SECTIONS = {
    "analyses": ("Analyses", "Launch and inspect AgencityLab analyses in a later development phase."),
    "compare": ("Compare", "Compare systems and analyses when scientific workflows are available."),
    "reports": ("Reports", "Build reproducible scientific reports in a later development phase."),
    "examples": ("Examples", "Explore curated examples when the example library is introduced."),
    "advanced": (
        "Advanced",
        "Experimental and research-facing modules will live here with explicit scientific status.",
    ),
}


def health(request):
    """Return a minimal liveness response without probing dependencies."""
    return JsonResponse({"status": "ok", "service": "AgencityStudio"})


def _database_status() -> str:
    try:
        connection.ensure_connection()
    except DatabaseError:  # pragma: no cover - backend failures are collapsed for operational safety
        return "unavailable"
    return "available"


def _broker_status() -> str:
    try:
        client = redis.Redis.from_url(
            settings.CELERY_BROKER_URL,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        return "available" if client.ping() else "unavailable"
    except (redis.exceptions.RedisError, ValueError):  # pragma: no cover - collapsed status
        return "unavailable"


def _system_status_context() -> dict[str, str]:
    lab_version = get_lab_version()
    return {
        "database_status": _database_status(),
        "broker_status": _broker_status(),
        "lab_status": "compatible" if lab_is_compatible() else "incompatible",
        "lab_version": lab_version,
    }


def _dashboard_project_context(request) -> dict:
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
    if current is None:
        return {
            "recent_projects": (),
            "active_project_count": 0,
            "archived_project_count": 0,
            "recent_datasets": (),
            "dataset_count": 0,
            "can_create_project": False,
        }
    request.session["current_workspace_slug"] = current.workspace.slug
    projects = Project.objects.for_workspace(current.workspace)
    datasets = Dataset.objects.for_workspace(current.workspace)
    return {
        "recent_projects": list(
            projects.active().select_related("workspace", "created_by").order_by("-updated_at")[:5]
        ),
        "active_project_count": projects.active().count(),
        "archived_project_count": projects.archived().count(),
        "recent_datasets": list(
            datasets.select_related("project", "project__workspace", "current_version")
            .order_by("-updated_at")[:5]
        ),
        "dataset_count": datasets.count(),
        "can_create_project": can_create_project(request.user, current.workspace),
    }


def readiness(request):
    """Report whether required runtime dependencies are ready to serve work."""
    context = _system_status_context()
    ready = (
        context["database_status"] == "available"
        and context["broker_status"] == "available"
        and context["lab_status"] == "compatible"
    )
    return JsonResponse(
        {
            "status": "ready" if ready else "not-ready",
            "service": "AgencityStudio",
            "dependencies": {
                "database": context["database_status"],
                "broker": context["broker_status"],
                "agencitylab": {
                    "status": context["lab_status"],
                    "version": context["lab_version"],
                },
            },
        },
        status=200 if ready else 503,
    )


@login_required
def dashboard(request):
    """Render the authenticated dashboard with real Project and Dataset summaries only."""
    return render(
        request,
        "studio/dashboard.html",
        {
            "active_nav": "dashboard",
            "page_title": "Dashboard",
            **_system_status_context(),
            **_dashboard_project_context(request),
        },
    )


@login_required
def workspace_section(request, section: str):
    """Render a future-workspace shell without fabricating domain data."""
    if section not in SECTIONS:
        raise Http404
    title, description = SECTIONS[section]
    return render(
        request,
        "studio/section.html",
        {
            "active_nav": section,
            "page_title": title,
            "section_title": title,
            "section_description": description,
        },
    )


def about(request):
    """Render non-sensitive runtime and compatibility information."""
    return render(request, "studio/about.html", {"page_title": "System information"})


@login_required
def system_status_partial(request):
    """Render the refreshable runtime status panel used by HTMX."""
    return render(request, "components/system_status.html", _system_status_context())


def dev_ui(request):
    """Render the internal design-system reference page in development only."""
    if not settings.DEBUG:
        raise Http404
    return render(request, "studio/dev_ui.html", {"page_title": "UI reference"})


def error_403(request, exception=None):
    return render(request, "403.html", status=403)


def error_404(request, exception=None):
    return render(request, "404.html", status=404)


def error_500(request):
    return render(request, "500.html", status=500)
