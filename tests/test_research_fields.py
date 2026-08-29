from __future__ import annotations

import inspect
import io
from types import SimpleNamespace

import numpy as np

from analyses.research_capabilities import (
    OUT_OF_SCOPE,
    SUPPORTED,
    UNAVAILABLE,
    research_capabilities,
)
from analyses.research_contract import RESEARCH_RESULT_SCHEMA_VERSION
from analyses.research_result_reader import ResearchFieldResultReader
from analyses.research_results import serialize_research_result
from labbridge.research import (
    ResearchExecution,
    bridge_beta_to_phi,
    domain_wall_initial_field,
    execute_research_dynamics,
    make_boundary,
    make_grid,
    make_potential,
    public_fields_api,
    public_thermodynamics_api,
    vortex_initial_field,
)


def _fixture():
    x = np.linspace(-0.6, 0.6, 7, dtype=np.float64)
    phi0 = 0.12 * np.cos(np.pi * x).astype(np.float64)
    phi_dot0 = np.linspace(-0.01, 0.01, x.size, dtype=np.float64)
    return x, phi0, phi_dot0


def _direct(model="KLEIN_GORDON", *, boundary_kind="DIRICHLET", boundary_value=0.0):
    x, phi0, phi_dot0 = _fixture()
    fields = public_fields_api()
    grid = fields.UniformRectilinearGrid(axes=(x,))
    potential = fields.QuarticAgencityPotential(lambda_=0.7, mu=1.1)
    if boundary_kind == "DIRICHLET":
        boundary = fields.DirichletBoundary(value=boundary_value)
    elif boundary_kind == "PERIODIC":
        boundary = fields.PeriodicBoundary()
    else:
        boundary = fields.NeumannBoundary(gradient=boundary_value)
    kwargs = {
        "grid": grid,
        "potential": potential,
        "dt": 0.01,
        "n_steps": 5,
        "boundary": boundary,
        "metadata": {"fixture": "plan13"},
    }
    if model == "KLEIN_GORDON":
        result = fields.simulate_klein_gordon(phi0, phi_dot0, **kwargs)
    elif model == "DISSIPATIVE_KLEIN_GORDON":
        result = fields.simulate_dissipative_klein_gordon(phi0, phi_dot0, gamma=0.15, **kwargs)
    else:
        result = fields.simulate_tdgl(phi0, gamma=0.15, **kwargs)
    return result


def _bridged(model="KLEIN_GORDON", *, boundary_kind="DIRICHLET", boundary_value=0.0):
    x, phi0, phi_dot0 = _fixture()
    return execute_research_dynamics(
        model=model,
        phi0=phi0,
        phi_dot0=None if model == "TDGL" else phi_dot0,
        axes=(x,),
        lambda_=0.7,
        mu=1.1,
        gamma=0.15 if model != "KLEIN_GORDON" else None,
        dt_solver=0.01,
        n_steps=5,
        boundary_kind=boundary_kind,
        boundary_value=boundary_value,
        metadata={"fixture": "plan13"},
    )


def _assert_solution_equal(left, right):
    np.testing.assert_array_equal(left.times, right.times)
    np.testing.assert_array_equal(left.phi, right.phi)
    if left.phi_dot is None or right.phi_dot is None:
        assert left.phi_dot is right.phi_dot is None
    else:
        np.testing.assert_array_equal(left.phi_dot, right.phi_dot)
    assert tuple(left.spatial_shape) == tuple(right.spatial_shape)
    assert left.dynamics_name == right.dynamics_name
    assert left.boundary_name == right.boundary_name
    assert left.scientific_status == right.scientific_status
    assert left.solver_metadata == right.solver_metadata
    for first, second in zip(left.spatial_axes, right.spatial_axes, strict=True):
        np.testing.assert_array_equal(first, second)


def test_capability_inventory_is_explicit_and_does_not_offer_gravity_simulation():
    capabilities = research_capabilities()
    assert capabilities["observable_to_phi_bridge"]["classification"] == SUPPORTED
    assert capabilities["autonomous_field_dynamics"]["classification"] == SUPPORTED
    assert capabilities["coherent_structures"]["classification"] == SUPPORTED
    assert capabilities["topology"]["classification"] == SUPPORTED
    assert capabilities["thermodynamics"]["classification"] == SUPPORTED
    assert capabilities["gravity"]["classification"] == UNAVAILABLE
    assert capabilities["effective_beta_field"]["classification"] == OUT_OF_SCOPE
    assert capabilities["quantum"]["classification"] == OUT_OF_SCOPE
    assert capabilities["cosmology"]["classification"] == OUT_OF_SCOPE


def test_klein_gordon_labbridge_is_exact_public_lab_call():
    _assert_solution_equal(_direct(), _bridged().result)


def test_dissipative_klein_gordon_labbridge_is_exact_public_lab_call():
    _assert_solution_equal(
        _direct("DISSIPATIVE_KLEIN_GORDON"),
        _bridged("DISSIPATIVE_KLEIN_GORDON").result,
    )


def test_tdgl_labbridge_is_exact_public_lab_call_and_has_no_phi_dot():
    direct = _direct("TDGL")
    bridged = _bridged("TDGL").result
    _assert_solution_equal(direct, bridged)
    assert bridged.phi_dot is None


def test_boundary_mapping_matches_lab_and_boundary_choice_changes_solution():
    fields = public_fields_api()
    assert isinstance(make_boundary(kind="PERIODIC"), fields.PeriodicBoundary)
    assert isinstance(make_boundary(kind="DIRICHLET", value=0.2), fields.DirichletBoundary)
    assert isinstance(make_boundary(kind="NEUMANN", value=0.1), fields.NeumannBoundary)
    periodic_direct = _direct(boundary_kind="PERIODIC")
    periodic_bridge = _bridged(boundary_kind="PERIODIC").result
    dirichlet = _bridged(boundary_kind="DIRICHLET").result
    _assert_solution_equal(periodic_direct, periodic_bridge)
    assert not np.array_equal(periodic_bridge.phi, dirichlet.phi)


def test_observable_bridge_is_explicit_exact_and_beta_is_not_phi_when_scale_differs():
    beta = np.array([[1.0 + 2.0j, 0.5 - 0.25j], [0.2 + 0.1j, -0.3j]])
    p_c = np.array([4.0, 9.0])
    tau = np.array([0.25, 1.0])
    direct = public_fields_api().beta_to_phi(beta, p_c, tau, time_axis=0)
    bridged = bridge_beta_to_phi(beta=beta, P_c=p_c, tau=tau, time_axis=0)
    np.testing.assert_array_equal(bridged, direct)
    assert not np.array_equal(bridged, beta)


def test_domain_wall_and_vortex_initializers_are_public_lab_equivalent():
    fields = public_fields_api()
    x = np.linspace(-1.0, 1.0, 9)
    direct_wall = fields.domain_wall_profile(x, lambda_=0.8, mu=1.2, center=0.1, orientation=-1)
    studio_wall = domain_wall_initial_field(
        x=x, lambda_=0.8, mu=1.2, center=0.1, orientation=-1
    )
    np.testing.assert_array_equal(studio_wall, direct_wall)

    y = np.linspace(-0.8, 0.8, 7)
    xx, yy = np.meshgrid(x, y, indexing="ij")
    radial_profile = np.minimum(np.sqrt(xx * xx + yy * yy), 1.0)
    direct_vortex = fields.vortex_field(
        x=x,
        y=y,
        radial_profile=radial_profile,
        winding=1,
        lambda_=0.8,
        mu=1.2,
    )
    studio_vortex = vortex_initial_field(
        x=x,
        y=y,
        radial_profile=radial_profile,
        winding=1,
        lambda_=0.8,
        mu=1.2,
    )
    np.testing.assert_array_equal(studio_vortex, direct_vortex)


def test_explicit_topology_and_thermodynamics_are_public_lab_equivalent():
    fields = public_fields_api()
    thermo = public_thermodynamics_api()
    theta = np.linspace(0.0, 2.0 * np.pi, 9)
    phi0 = np.exp(1j * theta)
    phi_dot0 = 0.01j * phi0
    axis = np.arange(phi0.size, dtype=float)
    contour = tuple(range(phi0.size))
    execution = execute_research_dynamics(
        model="DISSIPATIVE_KLEIN_GORDON",
        phi0=phi0,
        phi_dot0=phi_dot0,
        axes=(axis,),
        lambda_=0.7,
        mu=1.1,
        gamma=0.2,
        dt_solver=0.001,
        n_steps=3,
        boundary_kind="PERIODIC",
        boundary_value=0.0,
        topology_contour_indices=contour,
        thermo_t_eff=2.5,
        thermo_entropy_a=0.3,
    )
    solution = execution.result
    grid = fields.UniformRectilinearGrid(axes=(axis,))
    direct_winding = np.asarray(
        [fields.phase_winding(frame.reshape(-1)[list(contour)]) for frame in solution.phi]
    )
    direct_power = np.asarray(
        [thermo.total_dissipated_power(frame, 0.2, grid) for frame in solution.phi_dot]
    )
    direct_entropy_production = np.asarray(
        [thermo.total_entropy_production(frame, 0.2, 2.5, grid) for frame in solution.phi_dot]
    )
    direct_field_entropy = np.asarray(
        [thermo.field_agencial_entropy(frame, 0.3, grid) for frame in solution.phi]
    )
    np.testing.assert_array_equal(execution.derived["phase_winding"], direct_winding)
    np.testing.assert_array_equal(execution.derived["total_dissipated_power"], direct_power)
    np.testing.assert_array_equal(
        execution.derived["total_entropy_production"], direct_entropy_production
    )
    np.testing.assert_array_equal(execution.derived["field_agencial_entropy"], direct_field_entropy)


def test_complex_research_artifact_preserves_dtype_shape_and_exact_values():
    fields = public_fields_api()
    axis = np.linspace(-1.0, 1.0, 6)
    phi0 = np.exp(1j * axis)
    result = fields.simulate_tdgl(
        phi0,
        fields.UniformRectilinearGrid(axes=(axis,)),
        fields.QuarticAgencityPotential(lambda_=0.5, mu=1.0),
        gamma=0.2,
        dt=0.002,
        n_steps=2,
        boundary=fields.PeriodicBoundary(),
    )
    execution = ResearchExecution(result=result, derived={}, warnings=())
    run = SimpleNamespace(
        pk="11111111-1111-1111-1111-111111111111",
        analysis_id="22222222-2222-2222-2222-222222222222",
        source_sha256="a" * 64,
        execution_fingerprint="b" * 64,
        agencitylab_version="1.2.0",
        studio_version="0.13.0",
        analysis_options={
            "model": "TDGL",
            "public_function": "agencitylab.fields.simulate_tdgl",
        },
    )
    serialized = serialize_research_result(execution=execution, run=run)
    with ResearchFieldResultReader(
        io.BytesIO(serialized.data),
        expected_schema=RESEARCH_RESULT_SCHEMA_VERSION,
        expected_run_id=str(run.pk),
    ) as reader:
        restored = reader.read_series("phi")
        np.testing.assert_array_equal(restored, result.phi)
        assert restored.dtype == result.phi.dtype
        assert restored.shape == result.phi.shape
        exact = reader.exact_point("phi", 1, (2,))
        assert exact == result.phi[1, 2]
        assert reader.read_manifest()["scientific_status"] == "RESEARCH"


def test_research_adapter_contains_no_private_lab_import_or_duplicated_numerics():
    import labbridge.research as module

    source = inspect.getsource(module)
    assert "agencitylab.core" not in source
    for forbidden in ("np.gradient", "np.diff", "np.roll", "solve_ivp", "fft"):
        assert forbidden not in source
