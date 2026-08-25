from django.urls import path

from . import views

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
]
