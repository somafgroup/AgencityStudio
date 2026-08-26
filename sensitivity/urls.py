from django.urls import path

from . import views

app_name = "sensitivity"

urlpatterns = [
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/sensitivity/",
        views.sensitivity_home,
        name="home",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/sensitivity/new/",
        views.sensitivity_new,
        name="new",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/sensitivity/review/",
        views.sensitivity_review,
        name="review",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/sensitivity/<uuid:study_id>/",
        views.sensitivity_detail,
        name="detail",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/sensitivity/<uuid:study_id>/status/",
        views.sensitivity_status,
        name="status",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/sensitivity/<uuid:study_id>/cancel/",
        views.sensitivity_cancel,
        name="cancel",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/sensitivity/<uuid:study_id>/rerun/",
        views.sensitivity_rerun,
        name="rerun",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/sensitivity/<uuid:study_id>/visualization/manifest/",
        views.sensitivity_manifest,
        name="manifest",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/sensitivity/<uuid:study_id>/visualization/chart/",
        views.sensitivity_chart,
        name="chart",
    ),
    path(
        "analyses/<uuid:analysis_id>/runs/<uuid:run_id>/sensitivity/<uuid:study_id>/visualization/table/",
        views.sensitivity_table,
        name="table",
    ),
]
