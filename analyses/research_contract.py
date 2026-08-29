"""Studio labels for public AgencityLab autonomous-field research APIs.

This module contains orchestration identifiers only. It deliberately contains no
field equation, topology equation, thermodynamic formula, or gravity equation.
"""

RESEARCH_ANALYSIS_KIND = "RESEARCH_FIELD"
RESEARCH_SCIENTIFIC_STATUS = "RESEARCH"
RESEARCH_RESULT_SCHEMA_VERSION = "research-field-v1"
RESEARCH_INPUT_SCHEMA_VERSION = "research-input-v1"

MODEL_KLEIN_GORDON = "KLEIN_GORDON"
MODEL_DISSIPATIVE_KLEIN_GORDON = "DISSIPATIVE_KLEIN_GORDON"
MODEL_TDGL = "TDGL"
MODEL_CHOICES = (
    (MODEL_KLEIN_GORDON, "Conservative Klein-Gordon"),
    (MODEL_DISSIPATIVE_KLEIN_GORDON, "Dissipative Klein-Gordon"),
    (MODEL_TDGL, "Overdamped TDGL"),
)

INITIAL_NPZ = "NPZ_ARRAY"
INITIAL_OBSERVABLE_BRIDGE = "OBSERVABLE_BRIDGE"
INITIAL_DOMAIN_WALL = "DOMAIN_WALL"
INITIAL_VORTEX_PROFILE = "VORTEX_PROFILE"
INITIAL_CHOICES = (
    (INITIAL_NPZ, "Pinned NPZ field array"),
    (INITIAL_OBSERVABLE_BRIDGE, "Explicit observable beta_obs to phi bridge"),
    (INITIAL_DOMAIN_WALL, "AgencityLab domain-wall reference"),
    (INITIAL_VORTEX_PROFILE, "AgencityLab vortex from supplied radial-profile array"),
)

BOUNDARY_PERIODIC = "PERIODIC"
BOUNDARY_DIRICHLET = "DIRICHLET"
BOUNDARY_NEUMANN = "NEUMANN"
BOUNDARY_CHOICES = (
    (BOUNDARY_PERIODIC, "Periodic"),
    (BOUNDARY_DIRICHLET, "Dirichlet"),
    (BOUNDARY_NEUMANN, "Neumann"),
)

PUBLIC_APIS = {
    MODEL_KLEIN_GORDON: "agencitylab.fields.simulate_klein_gordon",
    MODEL_DISSIPATIVE_KLEIN_GORDON: "agencitylab.fields.simulate_dissipative_klein_gordon",
    MODEL_TDGL: "agencitylab.fields.simulate_tdgl",
    "bridge": "agencitylab.fields.beta_to_phi",
    "domain_wall": "agencitylab.fields.domain_wall_profile",
    "vortex": "agencitylab.fields.vortex_field",
    "topology_winding": "agencitylab.fields.phase_winding",
    "thermo_dissipation": "agencitylab.thermodynamics.total_dissipated_power",
    "thermo_entropy_production": "agencitylab.thermodynamics.total_entropy_production",
    "thermo_field_entropy": "agencitylab.thermodynamics.field_agencial_entropy",
}

SCIENTIFIC_DISCLAIMER = (
    "These modules implement research-level mathematical extensions of the Theory of Agencity. "
    "Their availability in AgencityLab does not constitute experimental validation of the "
    "corresponding physical interpretation."
)

BETA_PHI_BOUNDARY = (
    "beta_obs(x,t) is an observable field derived from data; phi(x,t) is an autonomous "
    "research-level field. No implicit identity between them is permitted."
)
