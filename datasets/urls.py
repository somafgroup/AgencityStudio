from django.urls import path

from . import preparation_views, views

app_name = "datasets"

PROJECT_PREFIX = "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/datasets"
DATASET_PREFIX = PROJECT_PREFIX + "/<uuid:dataset_id>/<slug:dataset_slug>"
PREPARATION_PREFIX = DATASET_PREFIX + "/preparations/<uuid:preparation_id>"

urlpatterns = [
    path("datasets/", views.dataset_list, name="list"),
    path(PROJECT_PREFIX + "/", views.project_datasets, name="project-list"),
    path(PROJECT_PREFIX + "/import/", views.dataset_import, name="import"),
    path(DATASET_PREFIX + "/", views.dataset_overview, name="overview"),
    path(DATASET_PREFIX + "/status/", views.dataset_status, name="status"),
    path(DATASET_PREFIX + "/preview/", views.dataset_preview, name="preview"),
    path(DATASET_PREFIX + "/columns/", views.dataset_columns, name="columns"),
    path(DATASET_PREFIX + "/quality/", views.dataset_quality, name="quality"),
    path(DATASET_PREFIX + "/versions/", views.dataset_versions, name="versions"),
    path(DATASET_PREFIX + "/source/", views.dataset_source, name="source"),
    path(DATASET_PREFIX + "/settings/", views.dataset_settings, name="settings"),
    path(DATASET_PREFIX + "/prepare/", preparation_views.preparation_list, name="preparation-list"),
    path(DATASET_PREFIX + "/prepare/new/", preparation_views.preparation_create, name="preparation-create"),
    path(PREPARATION_PREFIX + "/", preparation_views.preparation_detail, name="preparation-detail"),
    path(PREPARATION_PREFIX + "/status/", preparation_views.preparation_status, name="preparation-status"),
    path(PREPARATION_PREFIX + "/steps/add/", preparation_views.preparation_add_step, name="preparation-add-step"),
    path(
        PREPARATION_PREFIX + "/steps/<int:step_index>/<str:action>/",
        preparation_views.preparation_step_action,
        name="preparation-step-action",
    ),
    path(PREPARATION_PREFIX + "/run/", preparation_views.preparation_run, name="preparation-run"),
    path(PREPARATION_PREFIX + "/duplicate/", preparation_views.preparation_duplicate, name="preparation-duplicate"),
    path(PREPARATION_PREFIX + "/rerun/", preparation_views.preparation_rerun, name="preparation-rerun"),
    path(PREPARATION_PREFIX + "/preview/", preparation_views.preparation_preview, name="preparation-preview"),
    path(PREPARATION_PREFIX + "/download/", preparation_views.preparation_download, name="preparation-download"),
    path(PREPARATION_PREFIX + "/delete/", preparation_views.preparation_delete, name="preparation-delete"),
    path(DATASET_PREFIX + "/versions/new/", views.dataset_new_version, name="new-version"),
    path(
        DATASET_PREFIX + "/versions/<uuid:version_id>/reprocess/",
        views.dataset_reprocess,
        name="reprocess",
    ),
    path(
        DATASET_PREFIX + "/versions/<uuid:version_id>/confirm/",
        views.dataset_confirm,
        name="confirm",
    ),
    path(
        DATASET_PREFIX + "/versions/<uuid:version_id>/download/",
        views.dataset_download,
        name="download",
    ),
    path(
        DATASET_PREFIX + "/versions/<uuid:version_id>/delete-failed/",
        views.failed_version_delete,
        name="delete-failed-version",
    ),
    path(DATASET_PREFIX + "/delete/", views.dataset_delete, name="delete"),
]
