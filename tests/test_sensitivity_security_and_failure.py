import pytest
from django.test import Client, override_settings
from django.urls import reverse

from labbridge.sensitivity import SensitivityLabError
from sensitivity.models import SensitivityResultArtifact, StudyStatus
from sensitivity.services import queue_sensitivity_study
from sensitivity.tasks import execute_sensitivity_study
from tests.test_analyses import _user
from tests.test_sensitivity import _tau_configuration
from tests.test_visualization import _completed_run
from workspaces.models import WorkspaceMembership, WorkspaceRole


@pytest.mark.django_db(transaction=True)
def test_lab_failure_is_safe_and_never_publishes_completed_artifact(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, _workspace, _analysis, run, _artifact = _completed_run(
            tmp_path,
            monkeypatch,
            owner_email="sensitivity-failure-owner@example.com",
        )
        monkeypatch.setattr("sensitivity.services._enqueue", lambda _study_id: None)
        study = queue_sensitivity_study(
            actor=owner,
            run=run,
            configuration=_tau_configuration(run),
        )

        def fail_lab(**_kwargs):
            raise SensitivityLabError(
                "intentional public Lab failure",
                category="LAB_SENSITIVITY_EXECUTION_ERROR",
            )

        monkeypatch.setattr("sensitivity.tasks.execute_tau_multiscale", fail_lab)
        assert execute_sensitivity_study(str(study.pk)) == "failed"

        study.refresh_from_db()
        assert study.status == StudyStatus.FAILED
        assert study.error_category == "LAB_SENSITIVITY_EXECUTION_ERROR"
        assert "AgencityLab rejected" in study.error_message
        assert study.result_sha256 == ""
        assert not SensitivityResultArtifact.objects.filter(study=study).exists()


@pytest.mark.django_db(transaction=True)
def test_viewer_only_sees_completed_sensitivity_studies(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, workspace, analysis, run, _artifact = _completed_run(
            tmp_path,
            monkeypatch,
            owner_email="sensitivity-viewer-owner@example.com",
        )
        viewer = _user("sensitivity-completed-only-viewer@example.com")
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=viewer,
            role=WorkspaceRole.VIEWER,
        )
        monkeypatch.setattr("sensitivity.services._enqueue", lambda _study_id: None)
        study = queue_sensitivity_study(
            actor=owner,
            run=run,
            configuration=_tau_configuration(run),
        )

        client = Client()
        client.force_login(viewer)
        home_url = reverse("sensitivity:home", args=(analysis.pk, run.pk))
        detail_url = reverse("sensitivity:detail", args=(analysis.pk, run.pk, study.pk))
        status_url = reverse("sensitivity:status", args=(analysis.pk, run.pk, study.pk))

        home = client.get(home_url)
        assert home.status_code == 200
        assert str(study.pk).encode() not in home.content
        assert client.get(detail_url).status_code == 404
        assert client.get(status_url).status_code == 404

        assert execute_sensitivity_study(str(study.pk)) == "completed"
        study.refresh_from_db()
        assert client.get(detail_url).status_code == 200


@pytest.mark.django_db(transaction=True)
def test_non_member_cannot_access_any_completed_sensitivity_result_endpoint(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, _workspace, analysis, run, _artifact = _completed_run(
            tmp_path,
            monkeypatch,
            owner_email="sensitivity-isolation-owner@example.com",
        )
        outsider = _user("sensitivity-isolation-outsider@example.com")
        monkeypatch.setattr("sensitivity.services._enqueue", lambda _study_id: None)
        study = queue_sensitivity_study(
            actor=owner,
            run=run,
            configuration=_tau_configuration(run),
        )
        assert execute_sensitivity_study(str(study.pk)) == "completed"

        client = Client()
        client.force_login(outsider)
        endpoint_names = (
            "detail",
            "manifest",
            "chart",
            "table",
        )
        for endpoint in endpoint_names:
            url = reverse(
                f"sensitivity:{endpoint}",
                args=(analysis.pk, run.pk, study.pk),
            )
            assert client.get(url).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_scale_inspector_selects_exact_stored_row_without_mutating_study(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, _workspace, analysis, run, _artifact = _completed_run(
            tmp_path,
            monkeypatch,
            owner_email="sensitivity-scale-inspector@example.com",
        )
        monkeypatch.setattr("sensitivity.services._enqueue", lambda _study_id: None)
        study = queue_sensitivity_study(
            actor=owner,
            run=run,
            configuration=_tau_configuration(run, values=(0.1, 0.2, 0.3)),
        )
        assert execute_sensitivity_study(str(study.pk)) == "completed"
        before_fingerprint = study.execution_fingerprint
        before_result_sha = study.result_sha256

        client = Client()
        client.force_login(owner)
        url = reverse("sensitivity:detail", args=(analysis.pk, run.pk, study.pk))
        response = client.get(f"{url}?scale=1")
        assert response.status_code == 200
        assert response.context["selected_row"]["index"] == 1
        assert response.context["selected_row"]["scale"] == pytest.approx(0.2)
        assert b"Selected scale" in response.content

        study.refresh_from_db()
        assert study.execution_fingerprint == before_fingerprint
        assert study.result_sha256 == before_result_sha
