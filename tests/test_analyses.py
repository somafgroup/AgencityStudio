import hashlib

import numpy as np
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import override_settings

from analyses.models import AnalysisResultArtifact, RunStatus, SourceType
from analyses.results import CANONICAL_SERIES, load_analysis_result_bytes, serialize_analysis_result
from analyses.services import configure_analysis, create_analysis, queue_analysis_run
from analyses.storage import read_analysis_result
from analyses.tasks import execute_analysis_run
from datasets.models import (
    DataPreparation,
    DataPreparationStatus,
    Dataset,
    DatasetColumn,
    DatasetColumnRole,
    DatasetColumnType,
    DatasetImportStatus,
    DatasetSourceFormat,
    DatasetSourceKind,
    DatasetVersion,
    PreparedDataArtifact,
)
from datasets.storage import dataset_storage
from labbridge.execution import execute_canonical_analysis
from labbridge.service import public_api
from projects.services import create_project
from systems.models import MemoryWindowMode, ObservableDefinition, System, SystemRevision
from workspaces.models import WorkspaceMembership, WorkspaceRole
from workspaces.services import create_organisation_workspace

User = get_user_model()
PASSWORD = "Scientific-Plan7-Password!42"


def _arrays():
    xi = np.arange(40, dtype=float) * 0.1
    u = np.sin(2.0 * np.pi * xi)
    return xi, u


def _kwargs(w=0.2, P_c=12.0):
    return {
        "A_ref": 1.5,
        "tau": 0.2,
        "w": w,
        "P_c": P_c,
        "unit": "rad",
        "coordinate_unit": "s",
        "power_unit": "W",
        "observable_kind": "angle",
        "domain": "mechanics",
        "mechanism": "deterministic test oscillator",
        "system_type": "test rotor",
        "environment": "test",
    }


def _assert_equivalent(direct, through_studio):
    for name in CANONICAL_SERIES:
        left = getattr(direct, name, None)
        right = getattr(through_studio, name, None)
        if left is None or right is None:
            assert left is right
        else:
            np.testing.assert_allclose(np.asarray(left), np.asarray(right), rtol=1e-13, atol=1e-13)
    assert direct.A_ref == through_studio.A_ref
    assert direct.tau == through_studio.tau
    np.testing.assert_allclose(np.asarray(direct.P_c), np.asarray(through_studio.P_c))


def test_labbridge_is_numerically_equivalent_to_public_lab_for_sinusoid():
    xi, u = _arrays()
    api = public_api()
    direct = api.compute_agencity(u=u, xi=xi, **_kwargs())
    bridged = execute_canonical_analysis(u=u, xi=xi, **_kwargs()).result
    _assert_equivalent(direct, bridged)


def test_labbridge_constant_signal_pc_zero_and_unspecified_w_match_lab():
    xi = np.arange(20, dtype=float) * 0.1
    u = np.full(20, 3.0)
    api = public_api()
    kwargs = _kwargs(w=None, P_c=0.0)
    direct = api.compute_agencity(u=u, xi=xi, **kwargs)
    bridged = execute_canonical_analysis(u=u, xi=xi, **kwargs).result
    _assert_equivalent(direct, bridged)
    assert bridged.memory_window == pytest.approx(0.2)
    assert np.all(bridged.b == 0)


def test_result_serialization_preserves_complex_dtype_and_schema():
    xi, u = _arrays()
    result = execute_canonical_analysis(u=u, xi=xi, **_kwargs()).result

    class Run:
        pk = "00000000-0000-0000-0000-000000000001"
        analysis_id = "00000000-0000-0000-0000-000000000002"
        source_sha256 = "a" * 64
        system_revision_id = "00000000-0000-0000-0000-000000000003"
        system_configuration_fingerprint = "b" * 64
        execution_fingerprint = "c" * 64
        agencitylab_version = "1.1.3"
        studio_version = "0.7.0"

    serialized = serialize_analysis_result(result=result, run=Run())
    assert serialized.sha256 == hashlib.sha256(serialized.data).hexdigest()
    stored = load_analysis_result_bytes(serialized.data, expected_run_id=Run.pk)
    assert stored.arrays["U"].dtype == result.U.dtype
    assert stored.arrays["beta"].dtype == result.beta.dtype
    assert stored.arrays["b"].dtype == result.b.dtype
    np.testing.assert_array_equal(stored.arrays["beta"], result.beta)
    inventory = {item["name"]: item for item in stored.manifest["series"]}
    assert inventory["beta"]["dtype"] == str(result.beta.dtype)


def _user(email):
    return User.objects.create_user(email=email, password=PASSWORD)


def _project_and_system(owner):
    workspace = create_organisation_workspace(owner=owner, name="Canonical Lab")
    project = create_project(actor=owner, workspace=workspace, name="Canonical Project", domain="mechanics")
    system = System.objects.create(project=project, name="Rotor", slug="rotor", created_by=owner)
    revision = SystemRevision.objects.create(
        system=system,
        revision_number=1,
        documentation_status="DOCUMENTED",
        domain="mechanics",
        system_type="test rotor",
        mechanism="deterministic test oscillator",
        environment="test",
        a_ref_value=1.5,
        a_ref_value_text="1.5",
        a_ref_unit="rad",
        a_ref_origin="CALIBRATION",
        a_ref_justification="Test calibration",
        tau_value=0.2,
        tau_value_text="0.2",
        tau_unit="s",
        tau_origin="CALIBRATION",
        tau_justification="Test structural time",
        w_mode=MemoryWindowMode.UNSPECIFIED,
        p_c_value=0.0,
        p_c_value_text="0",
        p_c_unit="W",
        p_c_origin="MANUFACTURER",
        p_c_justification="Zero is a valid characteristic-power contract regression case",
        configuration_fingerprint="f" * 64,
        created_by=owner,
    )
    observable = ObservableDefinition.objects.create(
        revision=revision,
        position=1,
        name="Rotor angle",
        symbol="theta",
        unit="rad",
        observable_kind="angle",
        nature="MEASUREMENT",
        is_primary=True,
    )
    System.objects.filter(pk=system.pk).update(current_revision=revision)
    system.refresh_from_db()
    return workspace, project, revision, observable


def _raw_source(owner, project):
    xi, u = _arrays()
    payload = "time,angle\n" + "".join(f"{t:.17g},{v:.17g}\n" for t, v in zip(xi, u, strict=True))
    raw = payload.encode("utf-8")
    dataset = Dataset.objects.create(project=project, name="Rotor data", slug="rotor-data", created_by=owner)
    path = f"tests/plan7/{dataset.pk}/source.csv"
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
        import_options={"encoding": "utf-8", "delimiter": ",", "has_header": True, "decimal_separator": "."},
        row_count=len(xi),
        column_count=2,
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
        source_name="angle",
        display_name="angle",
        inferred_type=DatasetColumnType.NUMERIC,
        role=DatasetColumnRole.OBSERVABLE,
        unit="rad",
    )
    Dataset.objects.filter(pk=dataset.pk).update(current_version=version)
    return version


@pytest.mark.django_db(transaction=True)
def test_raw_run_pins_source_system_executes_lab_and_reads_private_result(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner = _user("owner@example.com")
        _workspace, project, revision, observable = _project_and_system(owner)
        version = _raw_source(owner, project)
        monkeypatch.setattr("analyses.services._enqueue", lambda _run_id: None)
        analysis = create_analysis(
            actor=owner,
            project=project,
            name="Rotor canonical",
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
        original_hash = version.source_sha256
        assert run.source_dataset_version == version
        assert run.source_prepared_artifact is None
        assert run.source_sha256 == original_hash
        assert run.system_revision == revision
        assert run.parameter_snapshot["w"]["mode"] == MemoryWindowMode.UNSPECIFIED
        assert run.parameter_snapshot["P_c"]["value"] == 0.0

        assert execute_analysis_run(str(run.pk)) == "completed"
        run.refresh_from_db()
        assert run.status == RunStatus.COMPLETED
        assert run.agencitylab_version == "1.1.3"
        assert run.result_sha256
        assert AnalysisResultArtifact.objects.filter(run=run).count() == 1
        stored = read_analysis_result(run, verify_hash=True)
        xi, u = _arrays()
        direct = public_api().compute_agencity(
            u=u,
            xi=xi,
            A_ref=1.5,
            tau=0.2,
            w=None,
            P_c=0.0,
            unit="rad",
            coordinate_unit="s",
            power_unit="W",
            observable_kind="angle",
            domain="mechanics",
            mechanism="deterministic test oscillator",
            system_type="test rotor",
            environment="test",
        )
        for name in CANONICAL_SERIES:
            np.testing.assert_allclose(stored.arrays[name], getattr(direct, name), rtol=1e-13, atol=1e-13)
        version.refresh_from_db()
        assert version.source_sha256 == original_hash
        assert run.effective_context["requested_w"] is None
        assert run.effective_context["effective_w"] == pytest.approx(0.2)
        assert execute_analysis_run(str(run.pk)) == "already-finished"
        assert AnalysisResultArtifact.objects.filter(run=run).count() == 1


@pytest.mark.django_db
def test_analyst_can_run_viewer_cannot_and_foreign_workspace_cannot_create(tmp_path):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner = _user("owner-roles@example.com")
        workspace, project, _revision, _observable = _project_and_system(owner)
        version = _raw_source(owner, project)
        analyst = _user("analyst@example.com")
        viewer = _user("viewer@example.com")
        outsider = _user("outsider@example.com")
        WorkspaceMembership.objects.create(workspace=workspace, user=analyst, role=WorkspaceRole.ANALYST)
        WorkspaceMembership.objects.create(workspace=workspace, user=viewer, role=WorkspaceRole.VIEWER)
        analysis = create_analysis(
            actor=analyst,
            project=project,
            name="Analyst run",
            source_type=SourceType.RAW_DATASET_VERSION,
            source_id=str(version.pk),
        )
        with pytest.raises(PermissionDenied):
            create_analysis(actor=viewer, project=project, name="No", source_type=SourceType.RAW_DATASET_VERSION, source_id=str(version.pk))
        with pytest.raises(PermissionDenied):
            create_analysis(actor=outsider, project=project, name="No", source_type=SourceType.RAW_DATASET_VERSION, source_id=str(version.pk))
        assert analysis.created_by == analyst


@pytest.mark.django_db
def test_prepared_source_hash_and_lineage_are_pinned(tmp_path):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        owner = _user("prepared@example.com")
        _workspace, project, _revision, _observable = _project_and_system(owner)
        version = _raw_source(owner, project)
        preparation = DataPreparation.objects.create(
            source_version=version,
            name="Explicit resampling",
            status=DataPreparationStatus.READY,
            recipe=[],
            recipe_hash="r" * 64,
            created_by=owner,
        )
        data = b"time,angle\n0,0\n0.1,1\n0.2,0\n0.3,-1\n"
        path = f"tests/plan7/{preparation.pk}/prepared.csv"
        stored, size, digest = dataset_storage().save_chunks(path, (data,))
        artifact = PreparedDataArtifact.objects.create(
            preparation=preparation,
            storage_path=stored,
            size_bytes=size,
            prepared_sha256=digest,
            row_count=4,
            column_count=2,
            column_metadata=[
                {"position": 1, "source_position": 1, "source_name": "time", "display_name": "time", "unit": "s", "role": "TIME", "inferred_type": "NUMERIC", "missing_count": 0, "non_numeric_count": 0, "non_finite_count": 0},
                {"position": 2, "source_position": 2, "source_name": "angle", "display_name": "angle", "unit": "rad", "role": "OBSERVABLE", "inferred_type": "NUMERIC", "missing_count": 0, "non_numeric_count": 0, "non_finite_count": 0},
            ],
        )
        analysis = create_analysis(
            actor=owner,
            project=project,
            name="Prepared canonical",
            source_type=SourceType.PREPARED_DATA,
            source_id=str(artifact.pk),
        )
        assert analysis.draft_configuration["source_id"] == str(artifact.pk)
        assert analysis.draft_configuration["source_type"] == SourceType.PREPARED_DATA
        assert artifact.prepared_sha256 == digest
