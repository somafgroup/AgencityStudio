import hashlib

import numpy as np
import pytest
from django.test import Client, override_settings
from django.urls import reverse

from analyses.models import AnalysisResultArtifact, RunStatus, SourceType
from analyses.services import configure_analysis, create_analysis, queue_analysis_run
from analyses.storage import analysis_storage, open_analysis_result_reader, read_analysis_result
from analyses.tasks import execute_analysis_run
from analyses.visualization import (
    display_indices,
    exact_table_payload,
    sample_payload,
    series_payload,
)
from tests.test_analyses import _arrays, _project_and_system, _raw_source, _user
from workspaces.models import WorkspaceMembership, WorkspaceRole


def _completed_run(tmp_path, monkeypatch, *, owner_email="visualization-owner@example.com"):
    owner = _user(owner_email)
    workspace, project, revision, observable = _project_and_system(owner)
    version = _raw_source(owner, project)
    monkeypatch.setattr("analyses.services._enqueue", lambda _run_id: None)
    analysis = create_analysis(
        actor=owner,
        project=project,
        name="Canonical visualization",
        source_type=SourceType.RAW_DATASET_VERSION,
        source_id=str(version.pk),
    )
    configure_analysis(
        actor=owner,
        analysis=analysis,
        coordinate_position=1,
        observable_position=2,
        system_revision=revision,
        system_observable=observable,
    )
    run = queue_analysis_run(actor=owner, analysis=analysis)
    assert execute_analysis_run(str(run.pk)) == "completed"
    run.refresh_from_db()
    assert run.status == RunStatus.COMPLETED
    artifact = AnalysisResultArtifact.objects.get(run=run)
    return owner, workspace, analysis, run, artifact


@pytest.mark.django_db(transaction=True)
def test_result_reader_reads_manifest_range_and_exact_sample(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        _owner, _workspace, _analysis, run, artifact = _completed_run(tmp_path, monkeypatch)
        with open_analysis_result_reader(run, verify_hash=True) as reader:
            assert reader.read_manifest()["schema_version"] == "1"
            assert reader.sample_count == 40
            assert {"xi", "u", "theta", "U", "beta", "b"}.issubset(reader.available_series)

            beta = reader.read_series("beta")
            np.testing.assert_array_equal(reader.read_series_range("beta", start=7, stop=13), beta[7:13])
            sample = reader.read_sample(11, names=("xi", "theta", "U", "beta", "b"))
            assert sample["xi"] == reader.read_series("xi")[11]
            assert sample["theta"] == reader.read_series("theta")[11]
            assert sample["U"] == reader.read_series("U")[11]
            assert sample["beta"] == beta[11]
            assert sample["b"] == reader.read_series("b")[11]

        assert artifact.sha256 == run.result_sha256


@pytest.mark.django_db(transaction=True)
def test_complex_series_remain_lossless_through_reader_and_display_encoding(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        _owner, _workspace, _analysis, run, artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="complex-visualization@example.com"
        )
        stored = read_analysis_result(run, verify_hash=True)
        with open_analysis_result_reader(run) as reader:
            for name in ("U", "beta", "b"):
                exact = stored.arrays[name]
                read = reader.read_series(name)
                assert np.iscomplexobj(read)
                assert read.dtype == exact.dtype
                assert read.shape == exact.shape
                np.testing.assert_array_equal(read.real, exact.real)
                np.testing.assert_array_equal(read.imag, exact.imag)

            payload = sample_payload(reader, index=9, result_sha256=artifact.sha256)
            for name in ("U", "beta", "b"):
                value = stored.arrays[name][9]
                encoded = payload["values"][name]["value"]
                assert encoded["real"] == pytest.approx(float(np.real(value)))
                assert encoded["imag"] == pytest.approx(float(np.imag(value)))
                assert encoded["magnitude"] == pytest.approx(float(np.abs(value)))


@pytest.mark.django_db(transaction=True)
def test_display_decimation_preserves_original_indices_and_exact_selected_sample(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        _owner, _workspace, _analysis, run, artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="decimation@example.com"
        )
        before = artifact.sha256
        with open_analysis_result_reader(run) as reader:
            indices = display_indices(start=0, stop=reader.sample_count, max_points=7)
            assert indices[0] == 0
            assert indices[-1] == reader.sample_count - 1
            assert len(indices) <= 7

            payload = series_payload(
                reader,
                names=("beta",),
                start=0,
                stop=reader.sample_count,
                max_points=7,
                result_sha256=artifact.sha256,
            )
            returned_indices = [point["index"] for point in payload["series"]["beta"]["points"]]
            assert returned_indices == indices.tolist()
            assert payload["decimated"] is True

            selected_index = returned_indices[len(returned_indices) // 2]
            sample = sample_payload(reader, index=selected_index, result_sha256=artifact.sha256)
            exact = reader.read_series("beta")[selected_index]
            assert sample["values"]["beta"]["value"]["real"] == pytest.approx(float(exact.real))
            assert sample["values"]["beta"]["value"]["imag"] == pytest.approx(float(exact.imag))

        artifact.refresh_from_db()
        run.refresh_from_db()
        assert artifact.sha256 == before
        assert run.result_sha256 == before
        with analysis_storage().open(artifact.storage_path, "rb") as handle:
            assert hashlib.sha256(handle.read()).hexdigest() == before


@pytest.mark.django_db(transaction=True)
def test_theta_visualization_returns_stored_lab_theta_not_beta_phase(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, _workspace, analysis, run, artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="theta-regression@example.com"
        )
        stored = read_analysis_result(run, verify_hash=True)
        theta = stored.arrays["theta"]
        beta_phase = np.angle(stored.arrays["beta"])
        finite = np.isfinite(theta) & np.isfinite(beta_phase)
        differing = finite & ~np.isclose(theta, beta_phase, rtol=1e-9, atol=1e-9)
        assert differing.any(), "The Lab-backed fixture must contain samples where arg(beta) differs from stored Theta."

        client = Client()
        client.force_login(owner)
        url = reverse("analysis:visualization-series", args=(analysis.pk, run.pk))
        response = client.get(url, {"series": "theta", "max_points": 5000})
        assert response.status_code == 200
        payload = response.json()
        returned = np.asarray([point["value"] for point in payload["series"]["theta"]["points"]])
        np.testing.assert_array_equal(returned, theta)
        assert payload["result_sha256"] == artifact.sha256


@pytest.mark.django_db(transaction=True)
def test_visualization_endpoints_are_private_workspace_scoped_and_hide_storage_paths(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, workspace, analysis, run, artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="permissions-visualization@example.com"
        )
        viewer = _user("visualization-viewer@example.com")
        outsider = _user("visualization-outsider@example.com")
        WorkspaceMembership.objects.create(workspace=workspace, user=viewer, role=WorkspaceRole.VIEWER)

        manifest_url = reverse("analysis:visualization-manifest", args=(analysis.pk, run.pk))
        series_url = reverse("analysis:visualization-series", args=(analysis.pk, run.pk))
        sample_url = reverse("analysis:visualization-sample", args=(analysis.pk, run.pk))
        workspace_url = reverse("analysis:results", args=(analysis.pk, run.pk))

        for member in (owner, viewer):
            client = Client()
            client.force_login(member)
            manifest_response = client.get(manifest_url)
            assert manifest_response.status_code == 200
            assert manifest_response["Cache-Control"] == "private, no-store"
            body = manifest_response.content.decode("utf-8")
            assert artifact.storage_path not in body
            assert str(tmp_path) not in body
            assert "storage_path" not in body

            assert client.get(series_url, {"series": "u,beta", "max_points": 6}).status_code == 200
            assert client.get(sample_url, {"index": 3}).status_code == 200
            page = client.get(workspace_url)
            assert page.status_code == 200
            assert b"Explore the immutable canonical result" in page.content

        outsider_client = Client()
        outsider_client.force_login(outsider)
        assert outsider_client.get(manifest_url).status_code == 404
        assert outsider_client.get(series_url, {"series": "u"}).status_code == 404
        assert outsider_client.get(sample_url, {"index": 0}).status_code == 404
        assert outsider_client.get(workspace_url).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_exact_table_preserves_original_order_and_artifact_hash(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        _owner, _workspace, _analysis, run, artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="table-visualization@example.com"
        )
        before = artifact.sha256
        with open_analysis_result_reader(run) as reader:
            table = exact_table_payload(reader, start=5, stop=10, result_sha256=artifact.sha256)
            assert [row["index"] for row in table["rows"]] == [5, 6, 7, 8, 9]
            beta = reader.read_series("beta")
            beta_cell = next(cell for cell in table["rows"][0]["cells"] if cell["key"] == "beta")
            assert beta_cell["value"]["real"] == pytest.approx(float(beta[5].real))
            assert beta_cell["value"]["imag"] == pytest.approx(float(beta[5].imag))
        artifact.refresh_from_db()
        assert artifact.sha256 == before


@pytest.mark.django_db(transaction=True)
def test_missing_result_artifact_is_reported_without_recomputation(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, _workspace, analysis, run, artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="missing-result@example.com"
        )
        analysis_storage().delete(artifact.storage_path)
        client = Client()
        client.force_login(owner)

        manifest_url = reverse("analysis:visualization-manifest", args=(analysis.pk, run.pk))
        response = client.get(manifest_url)
        assert response.status_code == 409
        assert "not available" in response.json()["error"].lower()

        page = client.get(reverse("analysis:results", args=(analysis.pk, run.pk)))
        assert page.status_code == 200
        assert b"will not recalculate it automatically" in page.content


@pytest.mark.django_db(transaction=True)
def test_workspace_only_offers_series_present_in_manifest(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner, _workspace, analysis, run, _artifact = _completed_run(
            tmp_path, monkeypatch, owner_email="inventory@example.com"
        )
        client = Client()
        client.force_login(owner)
        response = client.get(
            reverse("analysis:visualization-series", args=(analysis.pk, run.pk)),
            {"series": "not_a_stored_quantity"},
        )
        assert response.status_code == 404

        with open_analysis_result_reader(run) as reader:
            xi, u = _arrays()
            np.testing.assert_array_equal(reader.read_series("xi"), xi)
            np.testing.assert_allclose(reader.read_series("u"), u, rtol=0, atol=1e-15)
