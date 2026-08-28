from django.urls import path

from . import (
    diagnostic_views,
    field_views,
    field_visualization_views,
    multivariate_views,
    multivariate_visualization_views,
    views,
    visualization_views,
)

app_name = "analysis"

urlpatterns = [
    path("workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/analyses/", views.project_analysis_list, name="project-list"),
    path("workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/analyses/new/", views.analysis_create, name="create"),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/analyses/new/multivariate/",
        multivariate_views.multivariate_create,
        name="multivariate-create",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/analyses/new/observable-field/",
        field_views.observable_field_create,
        name="field-create",
    ),
    path("analyses/<uuid:analysis_id>/", views.analysis_detail, name="detail"),
    path("analyses/<uuid:analysis_id>/configure/", views.analysis_configure, name="configure"),
    path("analyses/<uuid:analysis_id>/review/", views.analysis_review, name="review"),
    path(
        "analyses/<uuid:analysis_id>/multivariate/configure/",
        multivariate_views.multivariate_configure,
        name="multivariate-configure",
    ),
    path(
        "analyses/<uuid:analysis_id>/multivariate/review/",
        multivariate_views.multivariate_review,
        name="multivariate-review",
    ),
    path(
        "analyses/<uuid:analysis_id>/observable-field/configure/",
        field_views.observable_field_configure,
        name="field-configure",
    ),
    path(
        "analyses/<uuid:analysis_id>/observable-field/review/",
        field_views.observable_field_review,
        name="field-review",
    ),
    path("analyses/<uuid:analysis_id>/archive/", views.analysis_archive, name="archive"),
    path("analyses/<uuid:analysis_id>/restore/", views.analysis_restore, name="restore"),
    path("analyses/<uuid:analysis_id>/delete/", views.analysis_delete, name="delete"),
    path("analyses/<uuid:analysis_id>/runs/<uuid:run_id>/", views.run_detail, name="run-detail"),
    path("analyses/<uuid:analysis_id>/runs/<uuid:run_id>/status/", views.run_status, name="run-status"),
    path("analyses/<uuid:analysis_id>/runs/<uuid:run_id>/cancel/", views.run_cancel, name="run-cancel"),
    path("analyses/<uuid:analysis_id>/runs/<uuid:run_id>/rerun/", views.run_rerun, name="run-rerun"),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/multivariate/rerun/",
        multivariate_views.multivariate_rerun,
        name="multivariate-rerun",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/observable-field/rerun/",
        field_views.observable_field_rerun,
        name="field-rerun",
    ),
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
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/multivariate/results/",
        multivariate_visualization_views.multivariate_workspace,
        {"section": "overview"},
        name="multivariate-results",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/multivariate/results/<slug:section>/",
        multivariate_visualization_views.multivariate_workspace,
        name="multivariate-results-section",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/observable-field/results/",
        field_visualization_views.field_workspace,
        {"section": "overview"},
        name="field-results",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/observable-field/results/<slug:section>/",
        field_visualization_views.field_workspace,
        name="field-results-section",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/observable-field/manifest/",
        field_visualization_views.field_manifest,
        name="field-manifest",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/observable-field/heatmap/",
        field_visualization_views.field_heatmap,
        name="field-heatmap",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/observable-field/slice/",
        field_visualization_views.field_slice,
        name="field-slice",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/observable-field/point/",
        field_visualization_views.field_point,
        name="field-point",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/observable-field/trace/",
        field_visualization_views.field_trace,
        name="field-trace",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/multivariate/components/<int:position>/manifest/",
        multivariate_visualization_views.component_manifest,
        name="multivariate-component-manifest",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/multivariate/components/<int:position>/series/",
        multivariate_visualization_views.component_series,
        name="multivariate-component-series",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/multivariate/components/<int:position>/sample/",
        multivariate_visualization_views.component_sample,
        name="multivariate-component-sample",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/multivariate/aggregate/manifest/",
        multivariate_visualization_views.aggregate_manifest,
        name="multivariate-aggregate-manifest",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/multivariate/aggregate/series/",
        multivariate_visualization_views.aggregate_series,
        name="multivariate-aggregate-series",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/multivariate/aggregate/sample/",
        multivariate_visualization_views.aggregate_sample,
        name="multivariate-aggregate-sample",
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
