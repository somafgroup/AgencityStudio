# Research field extensions

Plan 13 exposes only research-level autonomous-field capabilities that are publicly available in AgencityLab 1.2.0. AgencityStudio remains an orchestration, provenance, storage and visualization layer; it does not reimplement the Research equations.

## Scientific hierarchy

| Layer | Object | Status |
| --- | --- | --- |
| Canonical scalar | `u(t) -> beta(t) -> b(t)` | `CANONICAL` |
| Observable spatial field | `u(x,t) -> beta_obs(x,t) -> b_obs(x,t)` | `EXPERIMENTAL` |
| Autonomous field | `phi(x,t)` and its autonomous dynamics | `RESEARCH` |

`beta_obs(x,t)` is derived from an observable through the local canonical temporal pipeline. `phi(x,t)` belongs to an autonomous research-level dynamical model. They are not interchangeable.

Successful numerical execution confirms software execution of the implemented research model. It does not constitute experimental validation of that model.

## Public AgencityLab 1.2.0 capabilities used by Studio

Studio uses public package surfaces only. No `agencitylab.core` import is permitted.

### Autonomous dynamics — SUPPORTED

The Research Field analysis integrates the public field solvers exposed by AgencityLab 1.2.0:

- `agencitylab.fields.simulate_klein_gordon`
- `agencitylab.fields.simulate_dissipative_klein_gordon`
- `agencitylab.fields.simulate_tdgl`

The Studio configuration freezes the selected model, exact initial field, exact spatial axes, boundary condition, model parameters, numerical `dt_solver`, step count, software versions and immutable output artifact. Numerical solver parameters are implementation choices and must not be confused with the observable-pipeline quantities `tau` or CRM window `w`.

### Observable-to-autonomous bridge — SUPPORTED, explicit only

AgencityLab 1.2.0 publicly exposes `agencitylab.fields.beta_to_phi`. Studio exposes this only as an explicit user-triggered Research initial-condition path. A completed Observable Field Run never starts autonomous dynamics automatically. The source Run, source result SHA-256, selected time index and public bridge function are frozen in Research provenance.

### Coherent-structure constructors — SUPPORTED as initializers

Public Lab helpers used by Studio include:

- `agencitylab.fields.domain_wall_profile`
- `agencitylab.fields.vortex_field`

These helpers construct theoretical initial fields. They are not Studio-side defect detectors. For vortex initialization, inputs required by the public Lab contract, including a supplied radial profile where required, remain explicit.

### Topology — SUPPORTED as explicit Lab post-processing

Studio can call public `agencitylab.fields.phase_winding` when the user supplies the ordered contour required by that API. Studio does not infer a contour, detect a vortex in JavaScript, or treat displayed `arg(phi)` as a topological invariant.

### Field thermodynamics — SUPPORTED subset

The integrated post-processing surface is limited to public AgencityLab functions that can be applied unambiguously to an immutable Research Field result:

- `total_dissipated_power`
- `total_entropy_production`
- `field_agencial_entropy`

Inputs such as effective temperature or entropy coefficients are explicit Research parameters. Studio does not infer temperature, entropy or dissipation from signal variance, noise, canonical `D`, or a visualization.

### Gravity — UNAVAILABLE as an executable Studio Research module

AgencityLab 1.2.0 exposes research primitives related to gravitational extensions, including residual/tensor helpers, but Plan 13 does not expose a complete public autonomous gravity solver suitable for an immutable Studio Research Run. Gravity therefore has no executable Studio menu or empty result tab in Plan 13.

The advanced theory may document additional gravitational, curved-spacetime, backreaction, quantum or cosmological extensions. Where no supported public AgencityLab 1.2.0 execution contract exists, Studio marks the capability unavailable or out of scope rather than reimplementing it.

## Reproducibility boundary

A queued Research Run pins:

- Research model and public Lab function;
- scientific status `RESEARCH`;
- exact initial `phi_0` and optional `phi_dot_0`;
- initial-condition source and SHA-256;
- spatial rank, shape, coordinate axes, spacing and axis order;
- boundary condition and explicit boundary value where applicable;
- model parameters and their provenance;
- numerical method (`dt_solver`, step count and Lab-returned solver metadata);
- AgencityLab, AgencityStudio and Python versions;
- execution fingerprint;
- immutable result SHA-256.

The initial-condition artifact and completed result artifact are private and immutable. Complex dtypes and N-dimensional shapes are preserved; there is no silent float downcast or scientific downsampling.

## Execution and resource limits

Research simulations execute through Celery. The task payload is the Run UUID; the worker reopens the immutable input artifact and calls the selected public Lab API.

Instance limits such as `RESEARCH_FIELD_MAX_ELEMENTS`, `RESEARCH_FIELD_MAX_STEPS` and `RESEARCH_FIELD_MAX_OUTPUT_BYTES` are operational safeguards, not scientific thresholds. Requests exceeding a configured limit are rejected rather than silently truncated.

## Visualization

Apache ECharts remains the chart engine. Visualization reads only immutable stored artifacts and never reruns AgencityLab. For complex `phi`, `Re(phi)`, `Im(phi)`, `|phi|` and `arg(phi)` are display representations only. Exact point inspection uses full stored values; display decimation never becomes an input to topology or thermodynamic calculations.

## Permissions and isolation

Research analyses reuse the existing Analysis permissions. Owner, Editor and Analyst behavior follows the current scientific Analysis policy; Viewer is read-only. Non-members and cross-workspace requests receive 404 responses. Research artifacts remain private.

## Scientific disclaimer

> These modules implement research-level mathematical extensions of the Theory of Agencity. Their availability in AgencityLab does not constitute experimental validation of the corresponding physical interpretation.
