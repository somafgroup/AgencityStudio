"""Audited AgencityLab 1.2.0 research-field capability inventory.

The inventory is intentionally explicit rather than optimistic. ``SUPPORTED``
means Studio has an executable integration in Plan 13. ``UNAVAILABLE`` means the
installed Lab exposes only lower-level primitives or lacks the complete public
contract needed by the requested Studio operation. ``OUT_OF_SCOPE`` means the
capability is public but belongs to a different scientific layer or a future
Plan.
"""

from __future__ import annotations

from copy import deepcopy


SUPPORTED = "SUPPORTED"
UNAVAILABLE = "UNAVAILABLE"
OUT_OF_SCOPE = "OUT_OF_SCOPE"

_CAPABILITIES = {
    "observable_to_phi_bridge": {
        "classification": SUPPORTED,
        "status": "RESEARCH",
        "public_api": "agencitylab.fields.beta_to_phi",
        "inputs": "beta, P_c, tau, time_axis",
        "outputs": "phi with the exact beta shape",
        "note": "Explicit user-triggered bridge only; beta_obs is never treated as phi implicitly.",
    },
    "autonomous_field_dynamics": {
        "classification": SUPPORTED,
        "status": "RESEARCH",
        "public_api": [
            "agencitylab.fields.simulate_klein_gordon",
            "agencitylab.fields.simulate_dissipative_klein_gordon",
            "agencitylab.fields.simulate_tdgl",
        ],
        "inputs": "phi0, optional phi_dot0, UniformRectilinearGrid, QuarticAgencityPotential, boundary, numerical parameters",
        "outputs": "DynamicalAgencityFieldSolution",
        "note": "Studio configures and stores; AgencityLab owns all field equations and time stepping.",
    },
    "coherent_structures": {
        "classification": SUPPORTED,
        "status": "RESEARCH",
        "public_api": [
            "agencitylab.fields.domain_wall_profile",
            "agencitylab.fields.vortex_field",
        ],
        "inputs": "explicit grid/model parameters; vortex additionally requires a caller-supplied radial-profile array",
        "outputs": "initial phi field",
        "note": "Generation/initialization is distinct from detection. Studio supplies no vortex profile formula.",
    },
    "topology": {
        "classification": SUPPORTED,
        "status": "RESEARCH",
        "public_api": "agencitylab.fields.phase_winding",
        "inputs": "explicit ordered contour values of autonomous phi",
        "outputs": "numerical phase winding float",
        "note": "Distinct from canonical/observable temporal winding. No browser-side defect detection.",
    },
    "thermodynamics": {
        "classification": SUPPORTED,
        "status": "RESEARCH",
        "public_api": [
            "agencitylab.thermodynamics.total_dissipated_power",
            "agencitylab.thermodynamics.total_entropy_production",
            "agencitylab.thermodynamics.field_agencial_entropy",
        ],
        "inputs": "stored phi/phi_dot trajectory plus explicit gamma, T_eff and/or a and the same grid",
        "outputs": "time-indexed public Lab thermodynamic quantities",
        "note": "No temperature, entropy or dissipation is inferred from signal noise or D.",
    },
    "gravity": {
        "classification": UNAVAILABLE,
        "status": "RESEARCH",
        "public_api": [
            "agencitylab.gravity.curved_field_residual",
            "agencitylab.gravity.einstein_equation_residual",
            "agencitylab.gravity.stress_energy_tensor",
            "agencitylab.gravity.metric_with_perturbation",
        ],
        "inputs": "caller-supplied geometric derivatives/tensors/metric data",
        "outputs": "algebraic densities or equation residuals",
        "note": "AgencityLab 1.2.0 exposes research evaluators but no public metric/Einstein dynamics solver. Studio therefore exposes no gravity simulation tab or synthetic curvature map.",
    },
    "effective_beta_field": {
        "classification": OUT_OF_SCOPE,
        "status": "RESEARCH",
        "public_api": "agencitylab.fields.effective_beta",
        "inputs": "Chapter-15 effective-beta model inputs",
        "outputs": "effective-beta research quantities",
        "note": "Explicitly separate in AgencityLab from both beta_obs and autonomous phi; Plan 13 is scoped to autonomous phi workflows.",
    },
    "quantum": {
        "classification": OUT_OF_SCOPE,
        "status": "SPECULATIVE",
        "public_api": "agencitylab.quantum",
        "inputs": "not audited for execution in Plan 13",
        "outputs": "not integrated",
        "note": "Excluded by the Plan 13 scientific boundary.",
    },
    "cosmology": {
        "classification": OUT_OF_SCOPE,
        "status": "SPECULATIVE",
        "public_api": None,
        "inputs": "not integrated",
        "outputs": "not integrated",
        "note": "Excluded by the Plan 13 scientific boundary.",
    },
}


def research_capabilities() -> dict:
    """Return a defensive copy of the fixed AgencityLab 1.2.0 audit."""

    return deepcopy(_CAPABILITIES)
