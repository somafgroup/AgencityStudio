from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("projects/", views.project_list, name="list"),
    path("projects/new/", views.project_create, name="create"),
    path(
        "workspaces/<slug:workspace_slug>/projects/new/",
        views.project_create,
        name="create-in-workspace",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/",
        views.project_overview,
        name="overview",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/activity/",
        views.project_activity,
        name="activity",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/settings/",
        views.project_settings,
        name="settings",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/duplicate/",
        views.project_duplicate,
        name="duplicate",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/archive/",
        views.project_archive,
        name="archive",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/restore/",
        views.project_restore,
        name="restore",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/delete/",
        views.project_delete,
        name="delete",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<uuid:project_id>/<slug:project_slug>/<slug:section>/",
        views.project_section,
        name="section",
    ),
]
