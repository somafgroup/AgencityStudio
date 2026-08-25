from django.urls import path

from . import views

app_name = "systems"

urlpatterns = [
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/systems/",
        views.system_list,
        name="project-list",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/systems/new/",
        views.system_create,
        name="create",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/systems/<uuid:system_id>/<slug:system_slug>/",
        views.system_detail,
        name="detail",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/systems/<uuid:system_id>/<slug:system_slug>/revise/",
        views.system_revise,
        name="revise",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/systems/<uuid:system_id>/<slug:system_slug>/revisions/<int:revision_number>/",
        views.system_revision_detail,
        name="revision-detail",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/systems/<uuid:system_id>/<slug:system_slug>/settings/",
        views.system_settings,
        name="settings",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/systems/<uuid:system_id>/<slug:system_slug>/duplicate/",
        views.system_duplicate,
        name="duplicate",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/systems/<uuid:system_id>/<slug:system_slug>/archive/",
        views.system_archive,
        name="archive",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/systems/<uuid:system_id>/<slug:system_slug>/restore/",
        views.system_restore,
        name="restore",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/systems/<uuid:system_id>/<slug:system_slug>/delete/",
        views.system_delete,
        name="delete",
    ),
]
