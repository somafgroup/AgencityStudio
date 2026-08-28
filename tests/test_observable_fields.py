from __future__ import annotations

import io

import numpy as np
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client

from analyses.field_contract import (
    FIELD_ANALYSIS_KIND,
    PARAMETER_MODE_SCALAR,
    PARAMETER_MODE_SPATIAL,
    POWER_MODE_SPACETIME,
    SPATIAL_AXES_EXPLICIT,
    WINDOW_MODE_UNSPECIFIED,
)
from analyses.field_creation import create_observable_field_analysis
from analyses.field_result_reader import ObservableFieldResultReader
from analyses.field_results import serialize_observable_field_result
from analyses.field_services import (
    configure_observable_field_analysis,
    queue_observable_field_run,
)
from analyses.field_storage import open_observable_field_result_reader
from analyses.models import RunStatus
from analyses.tasks import execute_analysis_run
from datasets.field_source import FieldSourceError, inspect_npz_source
from datasets.models import (
    Dataset,
    DatasetImportStatus,
    DatasetSourceKind,
    DatasetVersion,
)
from datasets.storage import dataset_storage
from labbridge.fields import execute_observable_field_analysis, public_fields_api
from labbridge.service import public_api
from projects.services import create_project
from systems.models import MemoryWindowMode, ObservableDefinition, System, SystemRevision
from workspaces.services import create_organisation_workspace

User = get_user_model()
PASSWORD = "Scientific-Plan12-Password!42"


def _signals_1d():
    t = np.arange(72, dtype=np.float64) * 0.05
    x = np.linspace(-1.0, 1.0, 5, dtype=np.float64)
    u = np.stack(
        [np.sin((1.0 + 0.12 * j) * 2.0 * np.pi * t) + 0.05 * j for j in range(x.size)],
        axis=1,
    )
    return t, x, u


def _signals_2d():
    t = np.arange(64, dtype=np.float64) * 0.04
    x = np.linspace(0.0, 1.0, 4, dtype=np.float64)
    y = np.linspace(-0.5, 0.5, 3, dtype=np.float64)
    u = np.empty((t.size, x.size, y.size), dtype=np.float64)
    for i in range(x.size):
        for j in range(y.size):
            u[:, i, j] = np.sin((1.0 + 0.08 * i + 0.04 * j) * 2.0 * np.pi * t) + 0.03 * i
    return t, x, y, u


def _assert_field_equal(left, right):
    assert left.status == right.status == "experimental"
    assert left.model == right.model == "observable_agencity_field"
    assert left.backend == right.backend == "numpy"
    assert left.time_axis == right.time_axis
    assert tuple(left.spatial_shape) == tuple(right.spatial_shape)
    for name in (
        "t",
        "u",
        "u_star",
        "X_star",
        "A_star",
        "M",
        "O",
        "D",
        "S",
        "J",
        "U",
        "beta",
        "b",
        "A_ref",
        "tau",
        "w",
        "P_c",
    ):
        np.testing.assert_array_equal(np.asarray(getattr(left, name)), np.asarray(getattr(right, name)))
    assert len(left.spatial_axes) == len(right.spatial_axes)
    for first, second in zip(left.spatial_axes, right.spatial_axes, strict=True):
        np.testing.assert_array_equal(first, second)


def test_field_labbridge_equals_direct_public_field_api_1d_with_maps_and_zero_power():
    t, x, u = _signals_1d()
    a_ref = np.linspace(0.9, 1.3, x.size)
    tau = np.linspace(0.18, 0.26, x.size)
    w = np.linspace(0.20, 0.30, x.size)
    p_c = np.array([0.0, 1.2, 2.0, 3.5, 0.7])
    kwargs = {
        "spatial_axes": (x,),
        "A_ref": a_ref,
        "tau": tau,
        "w": w,
        "P_c": p_c,
        "time_axis": 0,
        "metadata": {"fixture": "plan12-1d"},
    }
    direct = public_fields_api().compute_agencity_field(u, t, **kwargs)
    bridged = execute_observable_field_analysis(u=u, t=t, **kwargs).result
    _assert_field_equal(direct, bridged)
    assert bridged.beta_obs is bridged.beta
    assert bridged.b_obs is bridged.b
    assert np.all(bridged.b[:, 0] == 0)
    assert bridged.metadata["crm_scope"] == "temporal_only_independent_at_each_spatial_location"


def test_field_labbridge_equals_direct_public_field_api_2d_spacetime_power_and_w_none():
    t, x, y, u = _signals_2d()
    spatial_shape = (x.size, y.size)
    a_ref = np.linspace(0.8, 1.4, x.size * y.size).reshape(spatial_shape)
    tau = np.linspace(0.12, 0.24, x.size * y.size).reshape(spatial_shape)
    p_c = np.ones_like(u)
    p_c[:, 0, 0] = 0.0
    kwargs = {
        "spatial_axes": (x, y),
        "A_ref": a_ref,
        "tau": tau,
        "w": None,
        "P_c": p_c,
        "time_axis": 0,
        "metadata": {"fixture": "plan12-2d"},
    }
    direct = public_fields_api().compute_agencity_field(u, t, **kwargs)
    bridged = execute_observable_field_analysis(u=u, t=t, **kwargs).result
    _assert_field_equal(direct, bridged)
    assert bridged.metadata["w_mode"] == "fallback_w_equals_tau"
    np.testing.assert_array_equal(bridged.w, tau)
    assert np.all(bridged.b[:, 0, 0] == 0)


def test_field_local_positions_equal_direct_public_scalar_api():
    t, x, u = _signals_1d()
    result = public_fields_api().compute_agencity_field(
        u,
        t,
        spatial_axes=(x,),
        A_ref=np.linspace(0.9, 1.3, x.size),
        tau=np.linspace(0.18, 0.26, x.size),
        w=None,
        P_c=np.array([0.0, 1.2, 2.0, 3.5, 0.7]),
    )
    api = public_api()
    for index in (0, 2, 4):
        direct = api.compute_agencity(
            u=u[:, index],
            xi=t,
            A_ref=float(result.A_ref[index]),
            tau=float(result.tau[index]),
            w=None,
            P_c=float(result.P_c[index]),
        )
        for name in ("u_star", "X_star", "A_star", "M", "O", "D", "S", "J", "U", "beta", "b"):
            np.testing.assert_array_equal(
                np.asarray(getattr(result, name))[:, index], np.asarray(getattr(direct, name))
            )


def test_nonzero_time_axis_is_preserved_and_locally_equivalent():
    t, x, u_time_first = _signals_1d()
    u = np.transpose(u_time_first)  # representation fixture: source is explicitly (x, time)
    result = public_fields_api().compute_agencity_field(
        u,
        t,
        spatial_axes=(x,),
        A_ref=1.1,
        tau=0.2,
        w=None,
        P_c=2.0,
        time_axis=1,
    )
    assert result.u.shape == (x.size, t.size)
    assert result.time_axis == 1
    direct = public_api().compute_agencity(
        u=u[3, :], xi=t, A_ref=1.1, tau=0.2, w=None, P_c=2.0
    )
    np.testing.assert_array_equal(result.beta[3, :], direct.beta)
    np.testing.assert_array_equal(result.b[3, :], direct.b)


def test_bridge_passes_unspecified_w_as_literal_none(monkeypatch):
    t, x, u = _signals_1d()
    actual = public_fields_api()
    captured = {}

    class Proxy:
        @staticmethod
        def compute_agencity_field(*args, **kwargs):
            captured["w"] = kwargs["w"]
            return actual.compute_agencity_field(*args, **kwargs)

    monkeypatch.setattr("labbridge.fields.public_fields_api", lambda: Proxy)
    execute_observable_field_analysis(
        u=u,
        t=t,
        spatial_axes=(x,),
        A_ref=1.0,
        tau=0.2,
        w=None,
        P_c=1.0,
        time_axis=0,
    )
    assert captured["w"] is None


def _npz_bytes(**arrays):
    handle = io.BytesIO()
    np.savez(handle, **arrays)
    return handle.getvalue()


def test_npz_inspection_preserves_shapes_dtypes_hashes_and_rejects_object_dtype():
    t, x, u = _signals_1d()
    payload = _npz_bytes(u=u, t=t, x=x, power=np.ones(x.size, dtype=np.float64))
    summary = inspect_npz_source(io.BytesIO(payload))
    by_key = {item["key"]: item for item in summary["arrays"]}
    assert by_key["u"]["shape"] == list(u.shape)
    assert by_key["u"]["dtype"] == u.dtype.str
    assert len(by_key["u"]["npy_sha256"]) == 64
    assert summary["kind"] == "observable_spatial_field_source"

    bad = _npz_bytes(labels=np.asarray([{"unsafe": True}], dtype=object))
    with pytest.raises(FieldSourceError, match="object dtype"):
        inspect_npz_source(io.BytesIO(bad))


def _user(email):
    return User.objects.create_user(email=email, password=PASSWORD)


def _project_system(owner, *, explicit_w=False):
    workspace = create_organisation_workspace(owner=owner, name="Field Lab")
    project = create_project(actor=owner, workspace=workspace, name="Field Project", domain="mechanics")
    system = System.objects.create(
        project=project,
        name="Distributed oscillator",
        slug="distributed-oscillator",
        created_by=owner,
    )
    revision = SystemRevision.objects.create(
        system=system,
        revision_number=1,
        documentation_status="DOCUMENTED",
        domain="mechanics",
        system_type="observable distributed test system",
        mechanism="explicit fixture",
        environment="test",
        a_ref_value=1.1,
        a_ref_value_text="1.1",
        a_ref_unit="rad",
        a_ref_origin="CALIBRATION",
        a_ref_justification="Explicit reference amplitude",
        tau_value=0.2,
        tau_value_text="0.2",
        tau_unit="s",
        tau_origin="CALIBRATION",
        tau_justification="Explicit structural time",
        w_mode=MemoryWindowMode.EXPLICIT if explicit_w else MemoryWindowMode.UNSPECIFIED,
        w_value=0.25 if explicit_w else None,
        w_value_text="0.25" if explicit_w else "",
        w_unit="s",
        w_origin="CALIBRATION" if explicit_w else "",
        w_justification="Explicit memory window" if explicit_w else "",
        p_c_value=2.0,
        p_c_value_text="2.0",
        p_c_unit="W",
        p_c_origin="MANUFACTURER",
        p_c_justification="Explicit characteristic power",
        configuration_fingerprint="2" * 64,
        created_by=owner,
    )
    observable = ObservableDefinition.objects.create(
        revision=revision,
        position=1,
        name="Angle field",
        symbol="q",
        unit="rad",
        observable_kind="angle",
        nature="MEASUREMENT",
        is_primary=True,
    )
    System.objects.filter(pk=system.pk).update(current_revision=revision)
    return workspace, project, revision, observable


def _field_version(owner, project, **arrays):
    payload = _npz_bytes(**arrays)
    summary = inspect_npz_source(io.BytesIO(payload))
    dataset = Dataset.objects.create(
        project=project,
        name="Field source",
        slug=f"field-source-{Dataset.objects.count() + 1}",
        created_by=owner,
    )
    version_id = __import__("uuid").uuid4()
    path = f"tests/plan12/{dataset.pk}/{version_id}/source.npz"
    stored_path, size, digest = dataset_storage().save_chunks(path, (payload,))
    version = DatasetVersion.objects.create(
        id=version_id,
        dataset=dataset,
        version_number=1,
        source_kind=DatasetSourceKind.UPLOAD,
        source_format="NPZ",
        source_path=stored_path,
        original_filename="field.npz",
        source_size_bytes=size,
        source_sha256=digest,
        media_type="application/x-npz",
        import_status=DatasetImportStatus.READY,
        importer_id="studio.npz-field-v1",
        import_options={"field_source": True},
        inspection_summary=summary,
        created_by=owner,
        confirmed_by=owner,
    )
    Dataset.objects.filter(pk=dataset.pk).update(current_version=version)
    return version, payload


def _configuration(revision, observable, **overrides):
    values = {
        "u_key": "u",
        "t_key": "t",
        "time_axis": 0,
        "time_unit": "s",
        "observable_unit": "rad",
        "spatial_axes_mode": SPATIAL_AXES_EXPLICIT,
        "spatial_axis_keys": ["x"],
        "spatial_axis_names": ["x"],
        "spatial_axis_units": ["m"],
        "system_revision": revision,
        "system_observable": observable,
        "A_ref_mode": PARAMETER_MODE_SCALAR,
        "A_ref_map_key": "",
        "A_ref_map_provenance": "",
        "tau_mode": PARAMETER_MODE_SCALAR,
        "tau_map_key": "",
        "tau_map_provenance": "",
        "w_mode": WINDOW_MODE_UNSPECIFIED,
        "w_map_key": "",
        "w_map_provenance": "",
        "P_c_mode": PARAMETER_MODE_SCALAR,
        "P_c_map_key": "",
        "P_c_map_provenance": "",
        "field_description": "Measured distributed oscillator fixture",
    }
    values.update(overrides)
    return values


@pytest.mark.django_db(transaction=True)
def test_field_analysis_run_matches_direct_lab_and_preserves_immutable_artifact(monkeypatch):
    owner = _user("field-run@example.test")
    _workspace, project, revision, observable = _project_system(owner)
    t, x, u = _signals_1d()
    a_ref = np.linspace(0.9, 1.3, x.size)
    tau_map = np.linspace(0.17, 0.25, x.size)
    p_c = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    version, source_bytes = _field_version(
        owner, project, u=u, t=t, x=x, A_ref_map=a_ref, tau_map=tau_map, P_c_map=p_c
    )
    analysis = create_observable_field_analysis(
        actor=owner,
        project=project,
        name="Experimental observable field",
        description="Plan 12 fixture",
        source=version,
    )
    configure_observable_field_analysis(
        actor=owner,
        analysis=analysis,
        values=_configuration(
            revision,
            observable,
            A_ref_mode=PARAMETER_MODE_SPATIAL,
            A_ref_map_key="A_ref_map",
            A_ref_map_provenance="Calibration map supplied with source",
            tau_mode=PARAMETER_MODE_SPATIAL,
            tau_map_key="tau_map",
            tau_map_provenance="Structural-time map supplied by experiment metadata",
            P_c_mode=PARAMETER_MODE_SPATIAL,
            P_c_map_key="P_c_map",
            P_c_map_provenance="Characteristic-power map from manufacturer model",
        ),
    )
    monkeypatch.setattr("analyses.field_services._enqueue", lambda run_id: None)
    run = queue_observable_field_run(actor=owner, analysis=analysis)
    assert run.analysis.analysis_kind == FIELD_ANALYSIS_KIND
    assert run.parameter_snapshot["w"]["requested_value"] is None
    assert run.parameter_snapshot["A_ref"]["npy_sha256"]
    assert run.mapping_snapshot["field_shape"] == list(u.shape)

    assert execute_analysis_run(str(run.pk)) == "completed"
    run.refresh_from_db()
    assert run.status == RunStatus.COMPLETED
    assert run.result_sha256
    assert run.effective_context["scientific_status"] == "EXPERIMENTAL"
    assert run.effective_context["lab_w_mode"] == "fallback_w_equals_tau"

    direct = public_fields_api().compute_agencity_field(
        u,
        t,
        spatial_axes=(x,),
        A_ref=a_ref,
        tau=tau_map,
        w=None,
        P_c=p_c,
        time_axis=0,
        metadata={
            "source": f"AgencityStudio AnalysisRun {run.pk}",
            "source_sha256": run.source_sha256,
            "observable": "Angle field",
            "observable_unit": "rad",
            "time_unit": "s",
        },
    )
    with open_observable_field_result_reader(run, verify_hash=True) as reader:
        manifest = reader.read_manifest()
        assert manifest["scientific_status"] == "EXPERIMENTAL"
        assert manifest["crm_scope"] == "temporal_only_independent_at_each_spatial_location"
        assert manifest["aliases"] == {"beta_obs": "beta", "b_obs": "b"}
        for name in ("u", "M", "J", "U", "beta", "b", "A_ref", "tau", "w", "P_c"):
            stored = reader.read_series(name)
            expected = np.asarray(getattr(direct, name))
            np.testing.assert_array_equal(stored, expected)
            assert stored.dtype == expected.dtype
        np.testing.assert_array_equal(
            reader.spatial_point_series("beta_obs", (2,)), direct.beta[:, 2]
        )
        assert reader.exact_point("b_obs", 11, (4,)) == direct.b[11, 4]

    with dataset_storage().open(version.source_path, "rb") as handle:
        assert handle.read() == source_bytes
    version.refresh_from_db()
    assert version.source_sha256 == run.source_sha256

    with pytest.raises(ValidationError, match="immutable"):
        run.error_message = "mutation"
        run.save()


@pytest.mark.django_db(transaction=True)
def test_2d_field_spacetime_power_serialization_and_exact_indexing(monkeypatch):
    owner = _user("field-2d@example.test")
    _workspace, project, revision, observable = _project_system(owner)
    t, x, y, u = _signals_2d()
    p_c = np.ones_like(u) * 1.5
    p_c[:, 1, 2] = 0.0
    version, _payload = _field_version(owner, project, u=u, t=t, x=x, y=y, P_c_spacetime=p_c)
    analysis = create_observable_field_analysis(
        actor=owner, project=project, name="2D field", description="", source=version
    )
    configure_observable_field_analysis(
        actor=owner,
        analysis=analysis,
        values=_configuration(
            revision,
            observable,
            spatial_axis_keys=["x", "y"],
            spatial_axis_names=["x", "y"],
            spatial_axis_units=["m", "m"],
            P_c_mode=POWER_MODE_SPACETIME,
            P_c_map_key="P_c_spacetime",
            P_c_map_provenance="Explicit space-time characteristic-power field",
        ),
    )
    monkeypatch.setattr("analyses.field_services._enqueue", lambda run_id: None)
    run = queue_observable_field_run(actor=owner, analysis=analysis)
    assert run.parameter_snapshot["P_c"]["mode"] == POWER_MODE_SPACETIME
    assert execute_analysis_run(str(run.pk)) == "completed"
    run.refresh_from_db()
    with open_observable_field_result_reader(run) as reader:
        beta = reader.read_series("beta_obs")
        b = reader.read_series("b_obs")
        assert beta.shape == u.shape
        assert b.shape == u.shape
        assert beta.dtype.kind == "c"
        assert b.dtype.kind == "c"
        np.testing.assert_array_equal(reader.spatial_point_series("u", (1, 2)), u[:, 1, 2])
        assert reader.exact_point("b_obs", 7, (1, 2)) == b[7, 1, 2]
        exact_slice = reader.spatial_slice(
            "b_obs", time_index=7, display_dimensions=(0, 1), fixed_indices={}
        )
        np.testing.assert_array_equal(exact_slice, b[7, :, :])
        assert np.all(b[:, 1, 2] == 0)


def test_lossless_complex_serialization_without_downcasting():
    t, x, u = _signals_1d()
    result = public_fields_api().compute_agencity_field(
        u, t, spatial_axes=(x,), A_ref=1.0, tau=0.2, w=None, P_c=2.0
    )

    class Run:
        pk = "00000000-0000-0000-0000-000000000001"
        analysis_id = "00000000-0000-0000-0000-000000000002"
        source_sha256 = "a" * 64
        system_revision_id = "00000000-0000-0000-0000-000000000003"
        system_configuration_fingerprint = "b" * 64
        execution_fingerprint = "c" * 64
        agencitylab_version = "1.1.3"
        studio_version = "0.12.0"
        mapping_snapshot = {
            "spatial_axes_mode": "EXPLICIT",
            "spatial_axes": [{"name": "x", "unit": "m", "length": len(x)}],
        }
        parameter_snapshot = {
            "A_ref": {"mode": "SCALAR"},
            "tau": {"mode": "SCALAR"},
            "w": {"mode": "UNSPECIFIED"},
            "P_c": {"mode": "SCALAR"},
        }
        analysis_options = {"public_function": "agencitylab.fields.compute_agencity_field"}

    serialized = serialize_observable_field_result(result=result, run=Run())
    with ObservableFieldResultReader(io.BytesIO(serialized.data), expected_run_id=str(Run.pk)) as reader:
        beta = reader.read_series("beta_obs")
        b = reader.read_series("b_obs")
        assert beta.dtype == result.beta.dtype
        assert b.dtype == result.b.dtype
        assert beta.shape == result.beta.shape
        assert b.shape == result.b.shape
        np.testing.assert_array_equal(beta, result.beta)
        np.testing.assert_array_equal(b, result.b)


@pytest.mark.django_db(transaction=True)
def test_wrong_parameter_map_shape_is_rejected_before_run():
    owner = _user("field-wrong-shape@example.test")
    _workspace, project, revision, observable = _project_system(owner)
    t, x, u = _signals_1d()
    version, _payload = _field_version(owner, project, u=u, t=t, x=x, bad=np.ones(x.size + 1))
    analysis = create_observable_field_analysis(
        actor=owner, project=project, name="Wrong map", description="", source=version
    )
    with pytest.raises(ValidationError, match="exact shape"):
        configure_observable_field_analysis(
            actor=owner,
            analysis=analysis,
            values=_configuration(
                revision,
                observable,
                A_ref_mode=PARAMETER_MODE_SPATIAL,
                A_ref_map_key="bad",
                A_ref_map_provenance="Explicit but malformed calibration map",
            ),
        )


@pytest.mark.django_db(transaction=True)
def test_cross_workspace_field_result_endpoints_return_404(monkeypatch):
    owner = _user("field-owner@example.test")
    outsider = _user("field-outsider@example.test")
    _workspace, project, revision, observable = _project_system(owner)
    t, x, u = _signals_1d()
    version, _payload = _field_version(owner, project, u=u, t=t, x=x)
    analysis = create_observable_field_analysis(
        actor=owner, project=project, name="Private field", description="", source=version
    )
    configure_observable_field_analysis(
        actor=owner, analysis=analysis, values=_configuration(revision, observable)
    )
    monkeypatch.setattr("analyses.field_services._enqueue", lambda run_id: None)
    run = queue_observable_field_run(actor=owner, analysis=analysis)
    assert execute_analysis_run(str(run.pk)) == "completed"

    client = Client()
    client.force_login(outsider)
    urls = (
        f"/analyses/{analysis.pk}/runs/{run.pk}/observable-field/results/",
        f"/analyses/{analysis.pk}/runs/{run.pk}/observable-field/manifest/",
        f"/analyses/{analysis.pk}/runs/{run.pk}/observable-field/slice/?series=u&time=0&dims=0",
        f"/analyses/{analysis.pk}/runs/{run.pk}/observable-field/point/?time=0&spatial=0",
        f"/analyses/{analysis.pk}/runs/{run.pk}/observable-field/trace/?spatial=0",
    )
    for url in urls:
        assert client.get(url).status_code == 404
