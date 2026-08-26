import hashlib

import numpy as np
import pytest
from agencitylab.api import compute_agencity_spectrum, optimize_agencity_window
from django.core.exceptions import ValidationError
from django.test import Client, override_settings
from django.urls import reverse

from analyses.storage import analysis_storage
from labbridge.sensitivity import execute_tau_multiscale, execute_window_sensitivity
from sensitivity.configuration import generate_grid
from sensitivity.models import (
    GridType,
    SensitivityResultArtifact,
    SensitivityStudy,
    StudyStatus,
    StudyType,
)
from sensitivity.services import queue_sensitivity_study, sensitivity_review_snapshot
from sensitivity.storage import read_sensitivity_result
from sensitivity.tasks import execute_sensitivity_study
from tests.test_analyses import _arrays, _user
from tests.test_visualization import _completed_run
from workspaces.models import WorkspaceMembership, WorkspaceRole


def _tau_configuration(run, values=(0.1, 0.2, 0.3)):
    return {
        "study_type": StudyType.TAU_MULTISCALE,
        "grid_type": GridType.EXPLICIT,
        "grid_unit": run.parameter_snapshot["tau"]["unit"],
        "requested_grid": list(values),
        "generation": {"explicit_text": ",".join(str(value) for value in values)},
    }


def _window_configuration(run, values=(0.2, 0.4, 0.8)):
    return {
        "study_type": StudyType.W_SENSITIVITY,
        "grid_type": GridType.EXPLICIT,
        "grid_unit": run.parameter_snapshot["tau"]["unit"],
        "requested_grid": list(values),
        "generation": {"explicit_text": ",".join(str(value) for value in values)},
    }


def _assert_result_dict_arrays_equal(left, right, names):
    for name in names:
        np.testing.assert_allclose(
            np.asarray(left[name]),
            np.asarray(right[name]),
            rtol=1e-13,
            atol=1e-13,
            equal_nan=True,
        )


def test_tau_multiscale_labbridge_equals_direct_public_lab_and_preserves_unspecified_w():
    xi, u = _arrays()
    taus = [0.1, 0.2, 0.3]
    direct = compute_agencity_spectrum(
        u,
        xi,
        taus,
        A_ref=1.5,
        P_c=0.0,
        windows=None,
        return_full=False,
    )
    through = execute_tau_multiscale(
        u=u,
        xi=xi,
        taus=taus,
        A_ref=1.5,
        P_c=0.0,
        requested_w_mode="UNSPECIFIED",
        requested_w=None,
    ).result
    _assert_result_dict_arrays_equal(
        direct,
        through,
        ("tau", "w", "b", "beta", "b_mean", "b_rms", "beta_mean", "J_mean", "S_mean"),
    )
    np.testing.assert_array_equal(through["w"], through["tau"])
    assert through["window_mode"] == direct["window_mode"] == "w=tau fallback convention"
    assert np.all(through["b"] == 0.0j)


def test_tau_multiscale_explicit_w_remains_fixed_and_matches_direct_public_lab():
    xi, u = _arrays()
    taus = [0.1, 0.2, 0.3]
    direct = compute_agencity_spectrum(
        u,
        xi,
        taus,
        A_ref=1.5,
        P_c=12.0,
        windows=0.2,
        return_full=False,
    )
    through = execute_tau_multiscale(
        u=u,
        xi=xi,
        taus=taus,
        A_ref=1.5,
        P_c=12.0,
        requested_w_mode="EXPLICIT",
        requested_w=0.2,
    ).result
    _assert_result_dict_arrays_equal(direct, through, ("tau", "w", "b", "beta"))
    np.testing.assert_array_equal(through["w"], np.full(3, 0.2))
    assert through["window_mode"] == "explicit independent w"


def test_window_sensitivity_labbridge_equals_direct_public_lab_with_fixed_tau():
    xi, u = _arrays()
    candidates = [0.2, 0.4, 0.8]
    direct = optimize_agencity_window(
        u,
        xi,
        tau=0.2,
        A_ref=1.5,
        P_c=12.0,
        candidates=candidates,
        n_candidates=len(candidates),
    )
    through = execute_window_sensitivity(
        u=u,
        xi=xi,
        tau=0.2,
        A_ref=1.5,
        P_c=12.0,
        candidates=candidates,
    ).result
    _assert_result_dict_arrays_equal(
        direct,
        through,
        ("candidate_w", "phi2", "phi1_mean_abs_contrast", "eligible"),
    )
    assert through["tau"] == direct["tau"] == 0.2
    assert through["w_opt"] == direct["w_opt"]
    assert through["best_index"] == direct["best_index"]
    assert through["criterion"] == "Phi2 angular stability"


def test_grid_generation_is_explicit_and_deterministic():
    assert generate_grid(grid_type=GridType.EXPLICIT, explicit_values=[0.1, 0.3, 0.8]) == [
        0.1,
        0.3,
        0.8,
    ]
    np.testing.assert_array_equal(
        generate_grid(grid_type=GridType.LINEAR, start=0.1, stop=0.3, count=3),
        [0.1, 0.2, 0.3],
    )
    np.testing.assert_allclose(
        generate_grid(grid_type=GridType.LOG, start=0.1, stop=10.0, count=3),
        [0.1, 1.0, 10.0],
    )
    with pytest.raises(ValidationError):
        generate_grid(grid_type=GridType.EXPLICIT, explicit_values=[0.1, 0.1])
    with pytest.raises(ValidationError):
        generate_grid(grid_type=GridType.LINEAR, start=0.0, stop=1.0, count=3)


@pytest.mark.django_db(transaction=True)
def test_real_tau_study_worker_preserves_base_run_system_and_source_and_complex_arrays(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, _workspace, _analysis, run, canonical_artifact = _completed_run(
            tmp_path,
            monkeypatch,
            owner_email="sensitivity-worker@example.com",
        )
        canonical_sha = run.result_sha256
        source_sha = run.source_sha256
        revision = run.system_revision
        tau_before = revision.tau_value
        w_mode_before = revision.w_mode
        with analysis_storage().open(canonical_artifact.storage_path, "rb") as handle:
            canonical_bytes_sha = hashlib.sha256(handle.read()).hexdigest()

        monkeypatch.setattr("sensitivity.services._enqueue", lambda _study_id: None)
        study = queue_sensitivity_study(
            actor=owner,
            run=run,
            configuration=_tau_configuration(run),
        )
        assert study.status == StudyStatus.QUEUED
        assert study.canonical_result_sha256 == canonical_sha
        assert study.source_sha256 == source_sha
        assert study.study_configuration["semantics"]["requested_w_mode"] == "UNSPECIFIED"
        assert execute_sensitivity_study(str(study.pk)) == "completed"

        study.refresh_from_db()
        run.refresh_from_db()
        revision.refresh_from_db()
        assert study.status == StudyStatus.COMPLETED
        assert run.result_sha256 == canonical_sha
        assert run.source_sha256 == source_sha
        assert revision.tau_value == tau_before
        assert revision.w_mode == w_mode_before
        with analysis_storage().open(canonical_artifact.storage_path, "rb") as handle:
            assert hashlib.sha256(handle.read()).hexdigest() == canonical_bytes_sha

        stored = read_sensitivity_result(study, verify_hash=True)
        np.testing.assert_array_equal(stored.arrays["tau"], [0.1, 0.2, 0.3])
        np.testing.assert_array_equal(stored.arrays["w"], stored.arrays["tau"])
        assert np.iscomplexobj(stored.arrays["b"])
        assert np.iscomplexobj(stored.arrays["beta"])
        assert stored.arrays["b"].dtype == np.dtype("complex128")
        assert study.result_artifact.sha256 == study.result_sha256
        assert execute_sensitivity_study(str(study.pk)) == "already-finished"
        assert SensitivityResultArtifact.objects.filter(study=study).count() == 1


@pytest.mark.django_db(transaction=True)
def test_invalid_window_candidate_is_rejected_without_rounding_or_mutation(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        _owner, _workspace, _analysis, run, _artifact = _completed_run(
            tmp_path,
            monkeypatch,
            owner_email="sensitivity-invalid-window@example.com",
        )
        before = dict(run.parameter_snapshot)
        with pytest.raises(ValidationError, match="integer multiple"):
            sensitivity_review_snapshot(
                run=run,
                configuration=_window_configuration(run, values=(0.15, 0.2)),
            )
        run.refresh_from_db()
        assert run.parameter_snapshot == before
        assert not SensitivityStudy.objects.filter(analysis_run=run).exists()


@pytest.mark.django_db(transaction=True)
def test_fingerprint_tracks_exact_grid_and_finished_studies_are_immutable(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, _workspace, _analysis, run, _artifact = _completed_run(
            tmp_path,
            monkeypatch,
            owner_email="sensitivity-fingerprint@example.com",
        )
        monkeypatch.setattr("sensitivity.services._enqueue", lambda _study_id: None)
        first = queue_sensitivity_study(actor=owner, run=run, configuration=_tau_configuration(run))
        second = queue_sensitivity_study(actor=owner, run=run, configuration=_tau_configuration(run))
        changed = queue_sensitivity_study(
            actor=owner,
            run=run,
            configuration=_tau_configuration(run, values=(0.1, 0.2, 0.4)),
        )
        assert first.execution_fingerprint == second.execution_fingerprint
        assert changed.execution_fingerprint != first.execution_fingerprint
        assert execute_sensitivity_study(str(first.pk)) == "completed"
        first.refresh_from_db()
        first.error_message = "changed"
        with pytest.raises(ValidationError):
            first.save()
        artifact = first.result_artifact
        artifact.sha256 = "0" * 64
        with pytest.raises(ValidationError):
            artifact.save()


@pytest.mark.django_db(transaction=True)
def test_analyst_can_run_viewer_is_read_only_and_outsider_cannot_read_results(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        _owner, workspace, analysis, run, _artifact = _completed_run(
            tmp_path,
            monkeypatch,
            owner_email="sensitivity-permissions-owner@example.com",
        )
        analyst = _user("sensitivity-analyst@example.com")
        viewer = _user("sensitivity-viewer@example.com")
        outsider = _user("sensitivity-outsider@example.com")
        WorkspaceMembership.objects.create(workspace=workspace, user=analyst, role=WorkspaceRole.ANALYST)
        WorkspaceMembership.objects.create(workspace=workspace, user=viewer, role=WorkspaceRole.VIEWER)
        monkeypatch.setattr("sensitivity.services._enqueue", lambda _study_id: None)

        study = queue_sensitivity_study(
            actor=analyst,
            run=run,
            configuration=_tau_configuration(run),
        )
        assert study.created_by == analyst
        assert execute_sensitivity_study(str(study.pk)) == "completed"
        study.refresh_from_db()

        detail_url = reverse("sensitivity:detail", args=(analysis.pk, run.pk, study.pk))
        chart_url = reverse("sensitivity:chart", args=(analysis.pk, run.pk, study.pk))
        new_url = reverse("sensitivity:new", args=(analysis.pk, run.pk))

        viewer_client = Client()
        viewer_client.force_login(viewer)
        assert viewer_client.get(detail_url).status_code == 200
        assert viewer_client.get(chart_url).status_code == 200
        assert viewer_client.get(new_url).status_code == 403

        outsider_client = Client()
        outsider_client.force_login(outsider)
        assert outsider_client.get(detail_url).status_code == 404
        assert outsider_client.get(chart_url).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_window_study_keeps_tau_fixed_and_preserves_lab_reported_optimum_as_result_only(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, _workspace, _analysis, run, _artifact = _completed_run(
            tmp_path,
            monkeypatch,
            owner_email="sensitivity-window-study@example.com",
        )
        monkeypatch.setattr("sensitivity.services._enqueue", lambda _study_id: None)
        tau_before = run.parameter_snapshot["tau"]["value"]
        study = queue_sensitivity_study(
            actor=owner,
            run=run,
            configuration=_window_configuration(run),
        )
        assert study.study_configuration["semantics"]["tau_fixed"] is True
        assert execute_sensitivity_study(str(study.pk)) == "completed"
        study.refresh_from_db()
        run.refresh_from_db()
        stored = read_sensitivity_result(study, verify_hash=True)
        assert stored.scalars["tau"] == tau_before
        assert stored.scalars["w_opt"] in stored.arrays["candidate_w"]
        assert stored.scalars["criterion"] == "Phi2 angular stability"
        assert run.parameter_snapshot["tau"]["value"] == tau_before
        assert run.parameter_snapshot["w"]["mode"] == "UNSPECIFIED"
