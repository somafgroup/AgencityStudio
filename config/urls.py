from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path

from analyses import research_views
from analyses import views as analysis_views
from common import views
from datasets import views as dataset_views

handler403 = "common.views.error_403"
handler404 = "common.views.error_404"
handler500 = "common.views.error_500"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("health/", views.health, name="health"),
    path("health/ready/", views.readiness, name="readiness"),
    path("accounts/", include("accounts.urls")),
    path("workspaces/", include("workspaces.urls")),
    path("datasets/", dataset_views.dataset_list, name="datasets"),
    path("analyses/", analysis_views.global_analysis_list, name="analyses"),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/",
        research_views.run_detail_dispatch,
    ),
    path("", include("datasets.urls")),
    path("", include("systems.urls")),
    path("", include("analyses.urls")),
    path("", include("sensitivity.urls")),
    path("", include("projects.urls")),
    path("admin/", admin.site.urls),
    path("compare/", views.workspace_section, {"section": "compare"}, name="compare"),
    path("reports/", views.workspace_section, {"section": "reports"}, name="reports"),
    path("examples/", views.workspace_section, {"section": "examples"}, name="examples"),
    path("advanced/", views.workspace_section, {"section": "advanced"}, name="advanced"),
    path("about/", login_required(views.about), name="about"),
    path("partials/system-status/", views.system_status_partial, name="system-status-partial"),
    path("dev/ui/", login_required(views.dev_ui), name="dev-ui"),
    path("i18n/", include("django.conf.urls.i18n")),
]
