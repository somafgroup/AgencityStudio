import numpy as np
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import override_settings

from analyses.models import (
    AnalysisResultArtifact,
    RunStatus,
    SourceType,
)
from analyses.multivariate_creation import create_multivariate_analysis
from analyses.multivariate_services import (
    configure_multivariate_analysis,
    queue_multivariate_run,
)
from analyses.multivariate_validation import (
    PARAMETER_MODE_COMPONENT_VECTOR,
    PARAMETER_MODE_SYSTEM_GLOBAL,
    WINDOW_MODE_UNSPECIFIED,
)
from analyses.storage import open_multivariate_result_reader
from analyses.tasks import execute_analysis_run
from datasets.models import (
    Dataset,
    DatasetColumn,
    DatasetColumnRole,
    DatasetColumnType,
    DatasetImportStatus,
    DatasetSourceFormat,
    DatasetSourceKind,
    DatasetVersion,
)
from datasets.storage import dataset_storage
from labbridge.multivariate import execute_multivariate_analysis
from labbridge.service import public_extended_api
from projects.services import create_project
from systems.models import MemoryWindowMode, ObservableDefinition, System, SystemRevision
from workspaces.models import WorkspaceMembership, WorkspaceRole
from workspaces.services import create_organisation_workspace

User = get_user_model()
PASSWORD = "Scientific-Plan11-Password!42"


def _signals():
    xi = np.arange(60, dtype=float) * 0.1
    component_a = np.sin(2.0 * np.pi * xi)
    component_b = 0.35 * np.cos(0.7 * np.pi * xi) + 0.15 * np.sin(1.3 * np.pi * xi)
    return xi, component_a, component_b


def _assert_public_multivariate_equal(left: dict, right: dict):
    for key in (
        "xi",
        "A_ref",
        "tau",
        "w",
        "P_c_components",
        "P_c_total",
        "beta_components",
        "b_components",
        "beta_multi",
        "beta_multi_defined",
        "b_total",
    ):
        np.testing.assert_array_equal(np.asarray(left[key]), np.asarray(right[key]))
    assert left["n_components"] == right["n_components"]
    assert left["aggregation"] == right["aggregation"]
    assert left["scientific_boundary"] == right["scientific_boundary"]
    assert len(left["components"]) == len(right["components"])
    for direct_component, bridged_component in zip(
        left["components"], right["components"], strict=True
    ):
        for key in (
            "xi",
            "u",
            "u_star",
            "t_star",
            "P_c",
            "X_star",
            "A_star",
            "M",
            "O",
            "D",
            "S",
            "J",
            "U",
            "theta",
            "beta",
            "b",
        ):
            np.testing.assert_array_equal(
                np.asarray(direct_component[key]),
                np.asarray(bridged_component[key]),
            )
        assert direct_component["A_ref"] == bridged_component["A_ref"]
        assert direct_component["tau"] == bridged_component["tau"]
        assert direct_component["w"] == bridged_component["w"]
        assert direct_component["window_mode"] == bridged_component["window_mode"]


def test_multivariate_labbridge_equals_direct_public_api_with_ordered_vectors():
    xi, component_a, component_b = _signals()
    matrix = np.column_stack((component_a, component_b))
    api = public_extended_api()
    kwargs = {
        "A_ref": [1.1, 0.8],
        "tau": [0.2, 0.3],
        "w": None,
        "P_c": [0.0, 3.5],
        "sample_axis": 0,
    }
    direct = api.compute_multivariate_agencity(matrix, xi, **kwargs)
    bridged = execute_multivariate_analysis(u=matrix, xi=xi, **kwargs).result
    _assert_public_multivariate_equal(direct, bridged)
    assert np.asarray(bridged["beta_components"]).dtype.kind == "c"
    assert np.asarray(bridged["b_total"]).dtype.kind == "c"
    assert bridged["w"][0] == pytest.approx(0.2)
    assert bridged["w"][1] == pytest.approx(0.3)
    assert np.all(np.asarray(bridged["b_components"])[0] == 0)


def _user(email):
    return User.objects.create_user(email=email, password=PASSWORD)


def _project_system(owner):
    workspace = create_organisation_workspace(owner=owner, name="Multivariate Lab")
    project = create_project(
        actor=owner,
        workspace=workspace,
        name="Multivariate Project",
        domain="mechanics",
    )
    system = System.objects.create(
        project=project,
        name="Vector rotor",
        slug="vector-rotor",
        created_by=owner,
    )
    revision = SystemRevision.objects.create(
        system=system,
        revision_number=1,
        documentation_status="DOCUMENTED",
        domain="mechanics",
        system_type="test vector rotor",
        mechanism="deterministic multicomponent oscillator",
        environment="test",
        a_ref_value=1.0,
        a_ref_value_text="1.0",
        a_ref_unit="rad",
        a_ref_origin="CALIBRATION",
        a_ref_justification="Explicit fixture reference amplitude",
        tau_value=0.2,
        tau_value_text="0.2",
        tau_unit="s",
        tau_origin="CALIBRATION",
        tau_justification="Explicit fixture structural time",
        w_mode=MemoryWindowMode.UNSPECIFIED,
        p_c_value=2.0,
        p_c_value_text="2.0",
        p_c_unit="W",
        p_c_origin="MANUFACTURER",
        p_c_justification="Explicit fixture characteristic power",
        configuration_fingerprint="1" * 64,
        created_by=owner,
    )
    observable_a = ObservableDefinition.objects.create(
        revision=revision,
        position=1,
        name="Rotor angle A",
        symbol="theta_A",
        unit="rad",
        observable_kind="angle",
        nature="MEASUREMENT",
        is_primary=True,
    )
    observable_b = ObservableDefinition.objects.create(
        revision=revision,
        position=2,
        name="Rotor angle B",
        symbol="theta_B",
        unit="rad",
        observable_kind="angle",
        nature="MEASUREMENT",
        is_primary=False,
    )
    System.objects.filter(pk=system.pk).update(current_revision=revision)
    return workspace, project, revision, observable_a, observable_b


def _raw_multivariate_source(owner, project):
    xi, component_a, component_b = _signals()
    payload = "time,component_a,component_b\n" + "".join(
        f"{t:.17g},{a:.17g},{b:.17g}\n"
        for t, a, b in zip(xi, component_a, component_b, strict=True)
    )
    raw = payload.encode("utf-8")
    dataset = Dataset.objects.create(
        project=project,
        name="Multivariate data",
        slug="multivariate-data",
        created_by=owner,
    )
    path = f"tests/plan11/{dataset.pk}/source.csv"
    stored_path, size, digest = dataset_storage().save_chunks(path, (raw,))
    version = DatasetVersion.objects.create(
        dataset=dataset,
        version_number=1,
        source_kind=DatasetSourceKind.UPLOAD,
        source_format=DatasetSourceFormat.CSV,
        source_path=stored_path,
        original_filename="source.csv",
        source_size_bytes=size,
        source_sha256=digest,
        import_status=DatasetImportStatus.READY,
        importer_id="studio.delimited",
        import_options={
            "encoding": "utf-8",
            "delimiter": ",",
            "has_header": True,
            "decimal_separator": ".",
        },
        row_count=len(xi),
        column_count=3,
        created_by=owner,
    )
    DatasetColumn.objects.create(
        dataset_version=version,
        position=1,
        source_name="time",
        display_name="time",
        inferred_type=DatasetColumnType.NUMERIC,
        role=DatasetColumnRole.TIME,
        unit="s",
    )
    DatasetColumn.objects.create(
        dataset_version=version,
        position=2,
        source_name="component_a",
        display_name="Component A",
        inferred_type=DatasetColumnType.NUMERIC,
        role=DatasetColumnRole.OBSERVABLE,
        unit="rad",
    )
    DatasetColumn.objects.create(
        dataset_version=version,
        position=3,
        source_name="component_b",
        display_name="Component B",
        inferred_type=DatasetColumnType.NUMERIC,
        role=DatasetColumnRole.OBSERVABLE,
        unit="rad",
    )
    Dataset.objects.filter(pk=dataset.pk).update(current_version=version)
    return version


def _global_components(observable_a, observable_b, *, reversed_order=False):
    values = [
        {"source_position": 2, "observable_id": str(observable_a.pk)},
        {"source_position": 3, "observable_id": str(observable_b.pk)},
    ]
    return list(reversed(values)) if reversed_order else values


def _vector_component(source_position, observable, *, a_ref, tau, p_c):
    common_origin = "CALIBRATION"
    return {
        "source_position": source_position,
        "observable_id": str(observable.pk),
        "A_ref": {
            "value": str(a_ref),
            "unit": "rad",
            "origin": common_origin,
            "justification": "Explicit component reference amplitude",
        },
        "tau": {
            "value": str(tau),
            "unit": "s",
            "origin": common_origin,
            "justification": "Explicit component structural time",
        },
        "P_c": {
            "value": str(p_c),
            "unit": "W",
            "origin": "MANUFACTURER",
            "justification": "Explicit component characteristic power",
        },
        "w": {},
    }


@pytest.mark.django_db(transaction=True)
def test_multivariate_run_preserves_order_parameters_complex_result_and_lab_aggregate(
    tmp_path, monkeypatch
):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner = _user("plan11-owner@example.com")
        _workspace, project, revision, observable_a, observable_b = _project_system(owner)
        revision.refresh_from_db()
        original_revision_fingerprint = revision.configuration_fingerprint
        version = _raw_multivariate_source(owner, project)
        monkeypatch.setattr("analyses.multivariate_services._enqueue", lambda _run_id: None)
        analysis = create_multivariate_analysis(
            actor=owner,
            project=project,
            name="Vector Run",
            source_type=SourceType.RAW_DATASET_VERSION,
            source_id=str(version.pk),
        )
        components = [
            _vector_component(2, observable_a, a_ref=1.1, tau=0.2, p_c=0.0),
            _vector_component(3, observable_b, a_ref=0.8, tau=0.3, p_c=3.5),
        ]
        configure_multivariate_analysis(
            actor=owner,
            analysis=analysis,
            coordinate_position=1,
            system_revision=revision,
            component_configs=components,
            parameter_modes={
                "A_ref": PARAMETER_MODE_COMPONENT_VECTOR,
                "tau": PARAMETER_MODE_COMPONENT_VECTOR,
                "w": WINDOW_MODE_UNSPECIFIED,
                "P_c": PARAMETER_MODE_COMPONENT_VECTOR,
            },
        )
        run = queue_multivariate_run(actor=owner, analysis=analysis)
        original_source_hash = version.source_sha256
        ordered = list(run.components.order_by("position"))
        assert [item.source_column_position for item in ordered] == [2, 3]
        assert [item.observable_definition_id for item in ordered] == [
            observable_a.pk,
            observable_b.pk,
        ]
        assert run.parameter_snapshot["call_contract"]["w"]["value"] is None
        assert run.parameter_snapshot["call_contract"]["P_c"]["value"] == [0.0, 3.5]

        assert execute_analysis_run(str(run.pk)) == "completed"
        run.refresh_from_db()
        assert run.status == RunStatus.COMPLETED
        assert run.result_sha256
        assert AnalysisResultArtifact.objects.filter(run=run).count() == 1
        assert "P_c_components" not in run.effective_context
        assert run.effective_context["P_c_components_shape"] == [2, 60]

        xi, component_a, component_b = _signals()
        matrix = np.column_stack((component_a, component_b))
        direct = public_extended_api().compute_multivariate_agencity(
            matrix,
            xi,
            A_ref=[1.1, 0.8],
            tau=[0.2, 0.3],
            w=None,
            P_c=[0.0, 3.5],
            sample_axis=0,
        )
        with open_multivariate_result_reader(run, verify_hash=True) as reader:
            np.testing.assert_array_equal(reader.read_aggregate("beta_multi"), direct["beta_multi"])
            np.testing.assert_array_equal(reader.read_aggregate("b_total"), direct["b_total"])
            np.testing.assert_array_equal(
                reader.read_aggregate("beta_multi_defined"),
                direct["beta_multi_defined"],
            )
            np.testing.assert_array_equal(
                reader.read_component(1, "beta"), direct["components"][0]["beta"]
            )
            np.testing.assert_array_equal(
                reader.read_component(2, "beta"), direct["components"][1]["beta"]
            )
            assert reader.read_component(1, "beta").dtype == np.asarray(
                direct["components"][0]["beta"]
            ).dtype
            assert reader.read_aggregate("b_total").dtype == np.asarray(direct["b_total"]).dtype
            manifest = reader.read_manifest()
            assert manifest["aggregation"] == direct["aggregation"]
            assert manifest["scientific_boundary"] == direct["scientific_boundary"]
            assert [item["observable_definition_id"] for item in manifest["components"]] == [
                str(observable_a.pk),
                str(observable_b.pk),
            ]

        version.refresh_from_db()
        revision.refresh_from_db()
        assert version.source_sha256 == original_source_hash
        assert revision.configuration_fingerprint == original_revision_fingerprint
        assert execute_analysis_run(str(run.pk)) == "already-finished"
        assert AnalysisResultArtifact.objects.filter(run=run).count() == 1
        component = run.components.order_by("position").first()
        component.display_name = "Mutation attempt"
        with pytest.raises(ValidationError):
            component.save()
        run.error_message = "Mutation attempt"
        with pytest.raises(ValidationError):
            run.save()


@pytest.mark.django_db
def test_component_order_changes_execution_fingerprint(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner = _user("plan11-order@example.com")
        _workspace, project, revision, observable_a, observable_b = _project_system(owner)
        version = _raw_multivariate_source(owner, project)
        monkeypatch.setattr("analyses.multivariate_services._enqueue", lambda _run_id: None)
        analysis = create_multivariate_analysis(
            actor=owner,
            project=project,
            name="Ordering",
            source_type=SourceType.RAW_DATASET_VERSION,
            source_id=str(version.pk),
        )
        modes = {
            "A_ref": PARAMETER_MODE_SYSTEM_GLOBAL,
            "tau": PARAMETER_MODE_SYSTEM_GLOBAL,
            "w": WINDOW_MODE_UNSPECIFIED,
            "P_c": PARAMETER_MODE_SYSTEM_GLOBAL,
        }
        configure_multivariate_analysis(
            actor=owner,
            analysis=analysis,
            coordinate_position=1,
            system_revision=revision,
            component_configs=_global_components(observable_a, observable_b),
            parameter_modes=modes,
        )
        first = queue_multivariate_run(actor=owner, analysis=analysis)
        configure_multivariate_analysis(
            actor=owner,
            analysis=analysis,
            coordinate_position=1,
            system_revision=revision,
            component_configs=[
                {"source_position": 3, "observable_id": str(observable_b.pk)},
                {"source_position": 2, "observable_id": str(observable_a.pk)},
            ],
            parameter_modes=modes,
        )
        second = queue_multivariate_run(actor=owner, analysis=analysis)
        assert first.execution_fingerprint != second.execution_fingerprint
        assert list(first.components.values_list("source_column_position", flat=True)) == [2, 3]
        assert list(second.components.values_list("source_column_position", flat=True)) == [3, 2]


@pytest.mark.django_db
def test_multivariate_result_endpoints_are_private_and_cross_workspace_safe(
    tmp_path, monkeypatch, client
):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner = _user("plan11-secure-owner@example.com")
        workspace, project, revision, observable_a, observable_b = _project_system(owner)
        version = _raw_multivariate_source(owner, project)
        viewer = _user("plan11-viewer@example.com")
        outsider = _user("plan11-outsider@example.com")
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=viewer,
            role=WorkspaceRole.VIEWER,
        )
        monkeypatch.setattr("analyses.multivariate_services._enqueue", lambda _run_id: None)
        analysis = create_multivariate_analysis(
            actor=owner,
            project=project,
            name="Private vector",
            source_type=SourceType.RAW_DATASET_VERSION,
            source_id=str(version.pk),
        )
        configure_multivariate_analysis(
            actor=owner,
            analysis=analysis,
            coordinate_position=1,
            system_revision=revision,
            component_configs=_global_components(observable_a, observable_b),
            parameter_modes={
                "A_ref": PARAMETER_MODE_SYSTEM_GLOBAL,
                "tau": PARAMETER_MODE_SYSTEM_GLOBAL,
                "w": WINDOW_MODE_UNSPECIFIED,
                "P_c": PARAMETER_MODE_SYSTEM_GLOBAL,
            },
        )
        run = queue_multivariate_run(actor=owner, analysis=analysis)
        assert execute_analysis_run(str(run.pk)) == "completed"
        run.refresh_from_db()

        client.force_login(viewer)
        response = client.get(
            f"/analyses/{analysis.pk}/runs/{run.pk}/multivariate/components/1/manifest/"
        )
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "private, no-store"

        client.force_login(outsider)
        for path in (
            f"/analyses/{analysis.pk}/runs/{run.pk}/multivariate/results/",
            f"/analyses/{analysis.pk}/runs/{run.pk}/multivariate/components/1/manifest/",
            f"/analyses/{analysis.pk}/runs/{run.pk}/multivariate/components/1/series/?series=beta",
            f"/analyses/{analysis.pk}/runs/{run.pk}/multivariate/components/1/sample/?index=0",
            f"/analyses/{analysis.pk}/runs/{run.pk}/multivariate/aggregate/manifest/",
        ):
            assert client.get(path).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_multivariate_nan_is_not_cleaned_and_failure_publishes_no_artifact(
    tmp_path, monkeypatch
):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner = _user("plan11-failure@example.com")
        _workspace, project, revision, observable_a, observable_b = _project_system(owner)
        version = _raw_multivariate_source(owner, project)
        monkeypatch.setattr("analyses.multivariate_services._enqueue", lambda _run_id: None)
        analysis = create_multivariate_analysis(
            actor=owner,
            project=project,
            name="Failure contract",
            source_type=SourceType.RAW_DATASET_VERSION,
            source_id=str(version.pk),
        )
        configure_multivariate_analysis(
            actor=owner,
            analysis=analysis,
            coordinate_position=1,
            system_revision=revision,
            component_configs=_global_components(observable_a, observable_b),
            parameter_modes={
                "A_ref": PARAMETER_MODE_SYSTEM_GLOBAL,
                "tau": PARAMETER_MODE_SYSTEM_GLOBAL,
                "w": WINDOW_MODE_UNSPECIFIED,
                "P_c": PARAMETER_MODE_SYSTEM_GLOBAL,
            },
        )
        run = queue_multivariate_run(actor=owner, analysis=analysis)

        def fail_lab(**_kwargs):
            from labbridge.multivariate import MultivariateLabError

            raise MultivariateLabError("LAB_VALIDATION_ERROR", "synthetic public Lab failure")

        monkeypatch.setattr(
            "analyses.multivariate_tasks.execute_multivariate_analysis",
            fail_lab,
        )
        assert execute_analysis_run(str(run.pk)) == "failed"
        run.refresh_from_db()
        assert run.status == RunStatus.FAILED
        assert run.error_category == "LAB_VALIDATION_ERROR"
        assert "synthetic public Lab failure" in run.error_message
        assert not AnalysisResultArtifact.objects.filter(run=run).exists()

        xi, component_a, component_b = _signals()
        matrix = np.column_stack((component_a, component_b))
        matrix[10, 1] = np.nan
        with pytest.raises(ValueError):
            public_extended_api().compute_multivariate_agencity(
                matrix,
                xi,
                A_ref=1.0,
                tau=0.2,
                w=None,
                P_c=2.0,
            )