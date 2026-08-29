from __future__ import annotations

import numpy as np
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, override_settings

from analyses.models import RunStatus, SourceType
from analyses.research_contract import INITIAL_DOMAIN_WALL, MODEL_KLEIN_GORDON
from analyses.research_services import (
    configure_research_field_analysis,
    create_research_field_analysis,
    queue_research_field_run,
    rerun_research_field,
    research_field_review_snapshot,
)
from analyses.research_storage import (
    open_research_input_reader,
    open_research_result_reader,
)
from analyses.tasks import execute_analysis_run
from projects.services import create_project
from workspaces.services import create_organisation_workspace

User = get_user_model()
PASSWORD = "Scientific-Plan13-Password!42"


def _owner(email="research-owner@example.test"):
    return User.objects.create_user(email=email, password=PASSWORD)


def _project(owner, name="Research Lab"):
    workspace = create_organisation_workspace(owner=owner, name=name)
    project = create_project(
        actor=owner,
        workspace=workspace,
        name=f"{name} Project",
        domain="research field fixture",
    )
    return workspace, project


def _configuration(**overrides):
    values = {
        "model": MODEL_KLEIN_GORDON,
        "initial_mode": INITIAL_DOMAIN_WALL,
        "initial_velocity_mode": "ZERO",
        "source": None,
        "phi_key": "",
        "phi_dot_key": "",
        "spatial_axis_keys_parsed": [],
        "observable_run": None,
        "observable_time_index": None,
        "generated_shape_parsed": [17],
        "generated_spacings_parsed": [0.25],
        "generated_origins_parsed": [-2.0],
        "domain_wall_center": 0.0,
        "domain_wall_orientation": "1",
        "vortex_winding": None,
        "radial_profile_key": "",
        "vortex_x_key": "",
        "vortex_y_key": "",
        "lambda_": 1.0,
        "lambda_origin": "dimensionless benchmark fixture",
        "mu": 1.0,
        "mu_origin": "dimensionless benchmark fixture",
        "gamma": None,
        "gamma_origin": "",
        "units_convention": "dimensionless",
        "boundary_kind": "DIRICHLET",
        "boundary_value_real": 0.0,
        "boundary_value_imag": 0.0,
        "dt_solver": 0.01,
        "n_steps": 4,
        "topology_contour_indices_parsed": [],
        "thermo_t_eff": None,
        "thermo_entropy_a": None,
    }
    values.update(overrides)
    return values


@pytest.mark.django_db(transaction=True)
def test_research_run_executes_from_immutable_input_without_system_revision(monkeypatch):
    owner = _owner()
    _workspace, project = _project(owner)
    analysis = create_research_field_analysis(
        actor=owner,
        project=project,
        name="Autonomous wall",
        description="Plan 13 deterministic fixture",
    )
    configure_research_field_analysis(
        actor=owner,
        analysis=analysis,
        values=_configuration(),
    )
    monkeypatch.setattr("analyses.research_services._enqueue", lambda run_id: None)
    run = queue_research_field_run(actor=owner, analysis=analysis)

    assert run.source_type == SourceType.RESEARCH_FIELD_INPUT
    assert run.system_revision is None
    assert run.system_observable is None
    assert run.analysis_options["scientific_status"] == "RESEARCH"
    assert run.analysis_options["initial_velocity_mode"] == "ZERO"
    assert run.source_snapshot["phi_dot_initialization"] == "USER_SELECTED_EXPLICIT_ZERO"
    assert run.research_input_artifact.sha256 == run.source_sha256
    with open_research_input_reader(run, verify_hash=True) as reader:
        phi0 = reader.read_series("phi0")
        phi_dot0 = reader.read_series("phi_dot0")
        assert phi0.shape == (17,)
        assert phi_dot0.shape == phi0.shape
        assert np.all(phi_dot0 == 0.0)
        assert reader.read_manifest()["scientific_status"] == "RESEARCH"

    assert execute_analysis_run(str(run.pk)) == "completed"
    run.refresh_from_db()
    assert run.status == RunStatus.COMPLETED
    assert run.result_sha256
    assert run.effective_context["scientific_status"] == "RESEARCH"
    assert run.effective_context["spatial_shape"] == [17]
    with open_research_result_reader(run, verify_hash=True) as reader:
        phi = reader.read_series("phi")
        phi_dot = reader.read_series("phi_dot")
        times = reader.read_series("times")
        assert phi.shape == (5, 17)
        assert phi_dot.shape == phi.shape
        assert times.shape == (5,)
        assert phi.dtype == np.dtype("float64")
        assert reader.read_manifest()["public_function"] == (
            "agencitylab.fields.simulate_klein_gordon"
        )

    with pytest.raises(ValidationError, match="immutable"):
        run.error_message = "do not mutate science"
        run.save()
    with pytest.raises(ValidationError, match="immutable"):
        run.result_artifact.manifest = {"mutated": True}
        run.result_artifact.save()
    with pytest.raises(ValidationError, match="immutable"):
        run.research_input_artifact.manifest = {"mutated": True}
        run.research_input_artifact.save()


@pytest.mark.django_db(transaction=True)
def test_exact_research_rerun_reuses_same_input_hash_and_fingerprint(monkeypatch):
    owner = _owner("research-rerun@example.test")
    _workspace, project = _project(owner, "Research Rerun Lab")
    analysis = create_research_field_analysis(actor=owner, project=project, name="Rerun", description="")
    configure_research_field_analysis(actor=owner, analysis=analysis, values=_configuration())
    monkeypatch.setattr("analyses.research_services._enqueue", lambda run_id: None)
    first = queue_research_field_run(actor=owner, analysis=analysis)
    assert execute_analysis_run(str(first.pk)) == "completed"
    first.refresh_from_db()
    second = rerun_research_field(actor=owner, run=first)
    assert second.source_sha256 == first.source_sha256
    assert second.execution_fingerprint == first.execution_fingerprint
    assert second.research_input_artifact.sha256 == first.research_input_artifact.sha256
    assert execute_analysis_run(str(second.pk)) == "completed"
    second.refresh_from_db()
    with open_research_result_reader(first) as left, open_research_result_reader(second) as right:
        np.testing.assert_array_equal(left.read_series("phi"), right.read_series("phi"))
        np.testing.assert_array_equal(left.read_series("phi_dot"), right.read_series("phi_dot"))


@pytest.mark.django_db(transaction=True)
@override_settings(RESEARCH_FIELD_MAX_STEPS=2)
def test_research_resource_limit_rejects_without_silent_truncation():
    owner = _owner("research-limit@example.test")
    _workspace, project = _project(owner, "Research Limit Lab")
    analysis = create_research_field_analysis(actor=owner, project=project, name="Too long", description="")
    with pytest.raises(ValidationError, match="instance limit is 2"):
        configure_research_field_analysis(
            actor=owner,
            analysis=analysis,
            values=_configuration(n_steps=3),
        )
    assert not analysis.runs.exists()


@pytest.mark.django_db(transaction=True)
def test_cross_workspace_research_endpoints_are_private_and_gravity_endpoint_is_absent(monkeypatch):
    owner = _owner("research-private-owner@example.test")
    outsider = _owner("research-private-outsider@example.test")
    _workspace, project = _project(owner, "Private Research Lab")
    analysis = create_research_field_analysis(
        actor=owner, project=project, name="Private Research", description=""
    )
    configure_research_field_analysis(actor=owner, analysis=analysis, values=_configuration())
    monkeypatch.setattr("analyses.research_services._enqueue", lambda run_id: None)
    run = queue_research_field_run(actor=owner, analysis=analysis)
    assert execute_analysis_run(str(run.pk)) == "completed"

    client = Client()
    client.force_login(outsider)
    urls = (
        f"/analyses/{analysis.pk}/runs/{run.pk}/research-field/results/",
        f"/analyses/{analysis.pk}/runs/{run.pk}/research-field/manifest/",
        f"/analyses/{analysis.pk}/runs/{run.pk}/research-field/slice/?time=0&dims=0",
        f"/analyses/{analysis.pk}/runs/{run.pk}/research-field/point/?time=0&spatial=0",
        f"/analyses/{analysis.pk}/runs/{run.pk}/research-field/trace/?spatial=0",
        f"/analyses/{analysis.pk}/runs/{run.pk}/research-field/derived/?series=phase_winding",
    )
    for url in urls:
        assert client.get(url).status_code == 404

    client.force_login(owner)
    assert client.get(f"/analyses/{analysis.pk}/runs/{run.pk}/research-field/gravity/").status_code == 404


@pytest.mark.django_db(transaction=True)
def test_research_review_freezes_numerical_method_separately_from_tau_and_w():
    owner = _owner("research-review@example.test")
    _workspace, project = _project(owner, "Research Review Lab")
    analysis = create_research_field_analysis(actor=owner, project=project, name="Review", description="")
    configure_research_field_analysis(actor=owner, analysis=analysis, values=_configuration())
    snapshot = research_field_review_snapshot(analysis)
    assert snapshot["config"]["dt_solver"] == 0.01
    assert snapshot["config"]["n_steps"] == 4
    assert "tau" not in snapshot["config"]
    assert "w" not in snapshot["config"]
    assert snapshot["scientific_status"] == "RESEARCH"
    assert "beta_obs(x,t) is an observable field" in snapshot["beta_phi_boundary"]
