from django.urls import path

from . import diagnostic_views, views, visualization_views

app_name = "analysis"

urlpatterns = [
    path("workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/analyses/", views.project_analysis_list, name="project-list"),
    path("workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/analyses/new/", views.analysis_create, name="create"),
    path("analyses/<uuid:analysis_id>/", views.analysis_detail, name="detail"),
    path("analyses/<uuid:analysis_id>/configure/", views.analysis_configure, name="configure"),
    path("analyses/<uuid:analysis_id>/review/", views.analysis_review, name="review"),
    path("analyses/<uuid:analysis_id>/archive/", views.analysis_archive, name="archive"),
    path("analyses/<uuid:analysis_id>/restore/", views.analysis_restore, name="restore"),
    path("analyses/<uuid:analysis_id>/delete/", views.analysis_delete, name="delete"),
    path("analyses/<uuid:analysis_id>/runs/<uuid:run_id>/", views.run_detail, name="run-detail"),
    path("analyses/<uuid:analysis_id>/runs/<uuid:run_id>/status/", views.run_status, name="run-status"),
    path("analyses/<uuid:analysis_id>/runs/<uuid:run_id>/cancel/", views.run_cancel, name="run-cancel"),
    path("analyses/<uuid:analysis_id>/runs/<uuid:run_id>/rerun/", views.run_rerun, name="run-rerun"),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/results/",
        visualization_views.result_workspace,
        {"section": "overview"},
        name="results",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/results/<slug:section>/",
        visualization_views.result_workspace,
        name="results-section",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/visualization/manifest/",
        visualization_views.visualization_manifest,
        name="visualization-manifest",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/visualization/series/",
        visualization_views.visualization_series,
        name="visualization-series",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/visualization/sample/",
        visualization_views.visualization_sample,
        name="visualization-sample",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/diagnostics/",
        diagnostic_views.diagnostics_home,
        name="diagnostics",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/diagnostics/new/",
        diagnostic_views.diagnostic_new,
        name="diagnostic-new",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/diagnostics/review/",
        diagnostic_views.diagnostic_review,
        name="diagnostic-review",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/diagnostics/<uuid:diagnostic_run_id>/",
        diagnostic_views.diagnostic_detail,
        name="diagnostic-detail",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/diagnostics/<uuid:diagnostic_run_id>/status/",
        diagnostic_views.diagnostic_status,
        name="diagnostic-status",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/diagnostics/<uuid:diagnostic_run_id>/cancel/",
        diagnostic_views.diagnostic_cancel,
        name="diagnostic-cancel",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/diagnostics/<uuid:diagnostic_run_id>/rerun/",
        diagnostic_views.diagnostic_rerun,
        name="diagnostic-rerun",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/diagnostics/<uuid:diagnostic_run_id>/workspace/",
        diagnostic_views.diagnostic_workspace,
        {"section": "overview"},
        name="diagnostic-workspace",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/diagnostics/<uuid:diagnostic_run_id>/workspace/<slug:section>/",
        diagnostic_views.diagnostic_workspace,
        name="diagnostic-workspace-section",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/diagnostics/<uuid:diagnostic_run_id>/visualization/manifest/",
        diagnostic_views.diagnostic_manifest,
        name="diagnostic-manifest",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/diagnostics/<uuid:diagnostic_run_id>/visualization/series/",
        diagnostic_views.diagnostic_series,
        name="diagnostic-series",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/diagnostics/<uuid:diagnostic_run_id>/visualization/sample/",
        diagnostic_views.diagnostic_sample,
        name="diagnostic-sample",
    ),
]
