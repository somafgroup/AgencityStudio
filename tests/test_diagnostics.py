import hashlib

import numpy as np
import pytest
from agencitylab import analyze_agencity
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, override_settings
from django.urls import reverse

from analyses.diagnostic_results import load_diagnostic_result_bytes
from analyses.diagnostic_services import queue_diagnostic_run
from analyses.diagnostic_storage import read_diagnostic_result
from analyses.diagnostic_tasks import execute_diagnostic_run
from analyses.diagnostic_validation import normalize_diagnostic_configuration
from analyses.models import DiagnosticResultArtifact, DiagnosticRun, RunStatus
from analyses.storage import analysis_storage, read_analysis_result
from labbridge.diagnostics import execute_diagnostics, rehydrate_public_result
from tests.test_analyses import _user
from tests.test_visualization import _completed_run
from workspaces.models import WorkspaceMembership, WorkspaceRole


def _default_configuration():
    return normalize_diagnostic_configuration({})


def _assert_float_sequence_equal(left, right):
    np.testing.assert_allclose(
        np.asarray(left, dtype=float),
        np.asarray(right, dtype=float),
        rtol=0,
        atol=0,
        equal_nan=True,
    )


@pytest.mark.django_db(transaction=True)
def test_labbridge_diagnostics_equal_direct_public_lab_bundle(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        _owner, _workspace, _analysis, run, _artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="diagnostic-equivalence@example.com"
        )
        stored = read_analysis_result(run, verify_hash=True)
        public_result = rehydrate_public_result(
            arrays=stored.arrays,
            manifest=stored.manifest,
        )
        direct = analyze_agencity(public_result)
        through_studio = execute_diagnostics(
            arrays=stored.arrays,
            manifest=stored.manifest,
            configuration=_default_configuration(),
        ).report

        assert through_studio["analysis_schema_version"] == direct["analysis_schema_version"] == "0.5"
        assert through_studio["regime"] == direct["regime"] == "undetermined"
        assert through_studio["real_agencity"]["status"] == direct["real_agencity"]["status"] == "undetermined"
        _assert_float_sequence_equal(
            through_studio["coherence"]["structural_orientation"]["sigma_theta"],
            direct["coherence"]["structural_orientation"]["sigma_theta"],
        )
        _assert_float_sequence_equal(
            through_studio["geometry"]["curvature"],
            direct["geometry"]["curvature"],
        )
        assert through_studio["transitions"] == direct["transitions"]
        assert through_studio["events"] == direct["events"]
        assert through_studio["regime_signature"] == direct["regime_signature"]


@pytest.mark.django_db(transaction=True)
def test_diagnostics_preserve_stored_theta_not_beta_phase(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        _owner, _workspace, _analysis, run, _artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="diagnostic-theta@example.com"
        )
        stored = read_analysis_result(run, verify_hash=True)
        theta = stored.arrays["theta"]
        beta_phase = np.angle(stored.arrays["beta"])
        finite = np.isfinite(theta) & np.isfinite(beta_phase)
        assert np.any(finite & ~np.isclose(theta, beta_phase, rtol=1e-9, atol=1e-9))

        public_result = rehydrate_public_result(arrays=stored.arrays, manifest=stored.manifest)
        np.testing.assert_array_equal(public_result.theta, theta)
        direct = analyze_agencity(public_result)
        through = execute_diagnostics(
            arrays=stored.arrays,
            manifest=stored.manifest,
            configuration=_default_configuration(),
        ).report
        _assert_float_sequence_equal(
            through["coherence"]["structural_orientation"]["sigma_theta"],
            direct["coherence"]["structural_orientation"]["sigma_theta"],
        )


@pytest.mark.django_db(transaction=True)
def test_default_configuration_invents_no_interpretive_thresholds(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        _owner, _workspace, _analysis, run, _artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="diagnostic-no-threshold@example.com"
        )
        stored = read_analysis_result(run, verify_hash=True)
        report = execute_diagnostics(
            arrays=stored.arrays,
            manifest=stored.manifest,
            configuration=_default_configuration(),
        ).report
        assert report["real_agencity"]["real_agencity"] is None
        assert report["real_agencity"]["thresholds"]["Sigma_Theta_max"] is None
        assert report["real_agencity"]["thresholds"]["abs_b_min"] is None
        assert report["regime"] == "undetermined"
        assert report["regime_classification"]["criteria"] is None
        assert report["structural_plateaus"]["status"] == "not configured"
        assert report["transitions"]["theta_jumps"]["status"] == "not configured"


@pytest.mark.django_db(transaction=True)
def test_explicit_real_agencity_thresholds_are_transmitted_and_preserved(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        _owner, _workspace, _analysis, run, _artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="diagnostic-thresholds@example.com"
        )
        stored = read_analysis_result(run, verify_hash=True)
        configuration = normalize_diagnostic_configuration(
            {
                "real_agencity": {
                    "theta_variance_threshold": 10.0,
                    "b_threshold": 0.0,
                    "min_fraction": 0.1,
                }
            }
        )
        direct = analyze_agencity(
            rehydrate_public_result(arrays=stored.arrays, manifest=stored.manifest),
            real_agencity_thresholds={
                "theta_variance_threshold": 10.0,
                "b_threshold": 0.0,
                "min_fraction": 0.1,
            },
        )
        through = execute_diagnostics(
            arrays=stored.arrays,
            manifest=stored.manifest,
            configuration=configuration,
        ).report
        assert through["real_agencity"]["thresholds"] == direct["real_agencity"]["thresholds"]
        assert through["real_agencity"]["real_agencity"] == direct["real_agencity"]["real_agencity"]
        assert through["real_agencity"]["real_agencity_fraction"] == pytest.approx(
            direct["real_agencity"]["real_agencity_fraction"]
        )


@pytest.mark.django_db(transaction=True)
def test_real_worker_pins_canonical_hash_and_publishes_immutable_diagnostic_artifact(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, _workspace, _analysis, run, canonical_artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="diagnostic-worker@example.com"
        )
        canonical_sha = run.result_sha256
        with analysis_storage().open(canonical_artifact.storage_path, "rb") as handle:
            canonical_bytes_sha = hashlib.sha256(handle.read()).hexdigest()
        monkeypatch.setattr("analyses.diagnostic_services._enqueue", lambda _run_id: None)
        diagnostic = queue_diagnostic_run(
            actor=owner,
            run=run,
            configuration=_default_configuration(),
        )
        assert diagnostic.status == RunStatus.QUEUED
        assert diagnostic.canonical_result_sha256 == canonical_sha
        assert execute_diagnostic_run(str(diagnostic.pk)) == "completed"
        diagnostic.refresh_from_db()
        run.refresh_from_db()
        assert diagnostic.status == RunStatus.COMPLETED
        assert diagnostic.result_sha256
        assert run.result_sha256 == canonical_sha
        with analysis_storage().open(canonical_artifact.storage_path, "rb") as handle:
            assert hashlib.sha256(handle.read()).hexdigest() == canonical_bytes_sha

        artifact = DiagnosticResultArtifact.objects.get(diagnostic_run=diagnostic)
        stored = read_diagnostic_result(diagnostic, verify_hash=True)
        assert stored.manifest["canonical_result_sha256"] == canonical_sha
        assert stored.report["real_agencity"]["status"] == "undetermined"
        assert artifact.sha256 == diagnostic.result_sha256
        assert execute_diagnostic_run(str(diagnostic.pk)) == "already-finished"
        assert DiagnosticResultArtifact.objects.filter(diagnostic_run=diagnostic).count() == 1


@pytest.mark.django_db(transaction=True)
def test_diagnostic_serialization_roundtrips_nonfinite_values_strictly(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, _workspace, _analysis, run, _artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="diagnostic-nonfinite@example.com"
        )
        monkeypatch.setattr("analyses.diagnostic_services._enqueue", lambda _run_id: None)
        diagnostic = queue_diagnostic_run(actor=owner, run=run, configuration=_default_configuration())
        assert execute_diagnostic_run(str(diagnostic.pk)) == "completed"
        diagnostic.refresh_from_db()
        artifact = diagnostic.result_artifact
        with analysis_storage().open(artifact.storage_path, "rb") as handle:
            raw = handle.read()
        stored = load_diagnostic_result_bytes(
            raw,
            expected_diagnostic_run_id=str(diagnostic.pk),
            expected_canonical_run_id=str(run.pk),
        )
        sigma = np.asarray(
            stored.report["coherence"]["structural_orientation"]["sigma_theta"],
            dtype=float,
        )
        assert np.isnan(sigma).any()


@pytest.mark.django_db(transaction=True)
def test_new_configuration_creates_new_diagnostic_run_without_mutating_history(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, _workspace, _analysis, run, _artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="diagnostic-history@example.com"
        )
        monkeypatch.setattr("analyses.diagnostic_services._enqueue", lambda _run_id: None)
        first = queue_diagnostic_run(actor=owner, run=run, configuration=_default_configuration())
        configured = normalize_diagnostic_configuration(
            {"theta_jumps": {"threshold": 1.0}}
        )
        second = queue_diagnostic_run(actor=owner, run=run, configuration=configured)
        first.refresh_from_db()
        assert first.run_number == 1
        assert second.run_number == 2
        assert first.diagnostic_configuration["theta_jumps"]["threshold"] is None
        assert second.diagnostic_configuration["theta_jumps"]["threshold"] == 1.0
        assert first.execution_fingerprint != second.execution_fingerprint


@pytest.mark.django_db(transaction=True)
def test_finished_diagnostic_run_and_artifact_are_immutable(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, _workspace, _analysis, run, _artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="diagnostic-immutable@example.com"
        )
        monkeypatch.setattr("analyses.diagnostic_services._enqueue", lambda _run_id: None)
        diagnostic = queue_diagnostic_run(actor=owner, run=run, configuration=_default_configuration())
        assert execute_diagnostic_run(str(diagnostic.pk)) == "completed"
        diagnostic.refresh_from_db()
        diagnostic.error_message = "changed"
        with pytest.raises(ValidationError):
            diagnostic.save()
        artifact = diagnostic.result_artifact
        artifact.sha256 = "0" * 64
        with pytest.raises(ValidationError):
            artifact.save()


@pytest.mark.django_db(transaction=True)
def test_viewer_can_inspect_but_cannot_run_and_outsider_gets_404(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, workspace, analysis, run, _artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="diagnostic-permissions@example.com"
        )
        monkeypatch.setattr("analyses.diagnostic_services._enqueue", lambda _run_id: None)
        diagnostic = queue_diagnostic_run(actor=owner, run=run, configuration=_default_configuration())
        assert execute_diagnostic_run(str(diagnostic.pk)) == "completed"
        diagnostic.refresh_from_db()

        viewer = _user("diagnostic-viewer@example.com")
        outsider = _user("diagnostic-outsider@example.com")
        WorkspaceMembership.objects.create(workspace=workspace, user=viewer, role=WorkspaceRole.VIEWER)

        detail_url = reverse(
            "analysis:diagnostic-detail", args=(analysis.pk, run.pk, diagnostic.pk)
        )
        workspace_url = reverse(
            "analysis:diagnostic-workspace", args=(analysis.pk, run.pk, diagnostic.pk)
        )
        manifest_url = reverse(
            "analysis:diagnostic-manifest", args=(analysis.pk, run.pk, diagnostic.pk)
        )
        new_url = reverse("analysis:diagnostic-new", args=(analysis.pk, run.pk))

        viewer_client = Client()
        viewer_client.force_login(viewer)
        assert viewer_client.get(detail_url).status_code == 200
        assert viewer_client.get(workspace_url).status_code == 200
        assert viewer_client.get(manifest_url).status_code == 200
        assert viewer_client.get(new_url).status_code == 403

        outsider_client = Client()
        outsider_client.force_login(outsider)
        assert outsider_client.get(detail_url).status_code == 404
        assert outsider_client.get(workspace_url).status_code == 404
        assert outsider_client.get(manifest_url).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_analyst_can_queue_diagnostics(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, workspace, _analysis, run, _artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="diagnostic-analyst-owner@example.com"
        )
        analyst = _user("diagnostic-analyst@example.com")
        WorkspaceMembership.objects.create(workspace=workspace, user=analyst, role=WorkspaceRole.ANALYST)
        monkeypatch.setattr("analyses.diagnostic_services._enqueue", lambda _run_id: None)
        diagnostic = queue_diagnostic_run(
            actor=analyst,
            run=run,
            configuration=_default_configuration(),
        )
        assert diagnostic.created_by == analyst
        assert diagnostic.status == RunStatus.QUEUED


@pytest.mark.django_db(transaction=True)
def test_canonical_hash_mismatch_blocks_diagnostic_execution(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, _workspace, _analysis, run, _artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="diagnostic-hash-mismatch@example.com"
        )
        monkeypatch.setattr("analyses.diagnostic_services._enqueue", lambda _run_id: None)
        diagnostic = queue_diagnostic_run(actor=owner, run=run, configuration=_default_configuration())
        DiagnosticRun.objects.filter(pk=diagnostic.pk).update(canonical_result_sha256="0" * 64)
        assert execute_diagnostic_run(str(diagnostic.pk)) == "failed"
        diagnostic.refresh_from_db()
        assert diagnostic.status == RunStatus.FAILED
        assert diagnostic.error_category == "RESULT_INPUT_ERROR"
        assert not DiagnosticResultArtifact.objects.filter(diagnostic_run=diagnostic).exists()
