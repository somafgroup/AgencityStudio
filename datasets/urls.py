from django.urls import path

from . import views

app_name = "datasets"

PROJECT_PREFIX = "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/datasets"
DATASET_PREFIX = PROJECT_PREFIX + "/<uuid:dataset_id>/<slug:dataset_slug>"

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
