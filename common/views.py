"""Views for the Plan 1 application shell and health surfaces."""

from django.conf import settings
from django.db import connection
from django.http import Http404, JsonResponse
from django.shortcuts import render

from labbridge.service import get_lab_version


SECTIONS = {
    "projects": ("Projects", "Organise scientific work into durable project spaces."),
    "datasets": ("Datasets", "Import and manage scientific data in a later development phase."),
    "analyses": ("Analyses", "Launch and inspect AgencityLab analyses in a later development phase."),
    "compare": ("Compare", "Compare systems and analyses when scientific workflows are available."),
    "reports": ("Reports", "Build reproducible scientific reports in a later development phase."),
    "examples": ("Examples", "Explore curated examples when the example library is introduced."),
    "advanced": ("Advanced", "Experimental and research-facing modules will live here with explicit scientific status."),
}


def health(request):
    """Return a minimal machine-readable process health response."""
    return JsonResponse({"status": "ok", "service": "AgencityStudio"})


def _database_status() -> str:
    try:
        connection.ensure_connection()
    except Exception:  # pragma: no cover - backend-specific failures are collapsed for UI safety
        return "unavailable"
    return "available"


def _system_status_context() -> dict[str, str]:
    lab_version = get_lab_version()
    return {
        "database_status": _database_status(),
        "lab_status": "available" if lab_version != "not-installed" else "not-installed",
        "lab_version": lab_version,
    }


def dashboard(request):
    """Render the honest, data-free initial scientific workspace dashboard."""
    return render(
        request,
        "studio/dashboard.html",
        {"active_nav": "dashboard", "page_title": "Dashboard", **_system_status_context()},
    )


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
