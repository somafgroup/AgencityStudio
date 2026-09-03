# Analyses, derived studies and field extensions

AgencityStudio separates canonical scalar execution, diagnostic interpretation, sensitivity exploration, multivariate execution, **EXPERIMENTAL observable spatial field** execution and **RESEARCH autonomous field** execution. Studio orchestrates public AgencityLab APIs; it is not a second scientific engine.

## Scientific execution boundaries

| Workflow | Scientific status | Public AgencityLab entry point |
| --- | --- | --- |
| Canonical scalar | CANONICAL local engine | `agencitylab.compute_agencity` |
| Diagnostics | diagnostic layer | `agencitylab.analyze_agencity` |
| Tau/window sensitivity | derived sensitivity layer | public multiscale/window APIs |
| Multivariate | public multivariate extension | public multivariate API |
| Observable spatial field | **EXPERIMENTAL** | `agencitylab.fields.compute_agencity_field` |
| Autonomous Research field | **RESEARCH** | public `agencitylab.fields.simulate_*` solvers |

A completed execution means the software call and immutable publication succeeded. It does not imply coherent or “real” agencity, nor does a completed Research field simulation experimentally validate its physical interpretation. `beta != 0`, non-zero local `beta_obs`, high `D` or large `b_obs` are not by themselves proof of real agencity.

## Analysis and AnalysisRun

`Analysis` is a mutable Project-owned workspace. `AnalysisRun` is the immutable reproducibility boundary for an exact execution. A queued Run freezes the exact scientific configuration, software versions, execution fingerprint and relevant source/input hashes before Celery executes the public Lab API.

Canonical/observable Runs pin source/System context as appropriate. A `RESEARCH_FIELD` Run instead pins an immutable `ResearchFieldInputArtifact` containing its exact autonomous initial state and grid; it does not fake a canonical `SystemRevision` relationship that the autonomous Lab solver does not require.

Historical finished Runs are immutable. Exactly one authoritative result artifact is published for a successful Run, and private storage paths are never exposed as public media URLs.

## Canonical scalar Analysis

Canonical scalar Runs pin an exact raw/prepared source, coordinate/observable mapping and scalar physical/contextual `A_ref`, `tau`, requested `w` and `P_c` snapshots. When `w` is unspecified, Studio passes `None`; it does not substitute `tau` before the public API call.

Completed scalar Runs publish `ZIP_NPY_JSON` artifacts preserving public returned arrays such as `xi`, `u`, `u_star`, `X_star`, `A_star`, `M`, `O`, `D`, `S`, `J`, `theta`, `U`, `beta` and `b` when present. Complex dtypes are preserved and pickle is disabled.

## DiagnosticRun — Plan 9

Diagnostics are immutable records downstream of one completed canonical Run. Studio reads the exact canonical artifact and reconstructs only the public result container required by `analyze_agencity`; it does not rerun canonical computation or implement diagnostic equations.

Stored canonical `theta` is authoritative for structural orientation. Studio never repairs missing orientation with `arg(beta)`. Diagnostic thresholds are public-Lab/default or explicit user configuration; absent criteria may legitimately produce `undetermined`.

## SensitivityStudy — Plan 10

Sensitivity studies pin one completed canonical Run and fixed context. Tau multiscale sends an exact requested tau grid to the public spectrum API. Window sensitivity sends exact explicit `w` candidates to the public optimization API.

`dt`, `tau` and `w` remain distinct. A multiscale maximum is not automatically physical `tau`; Lab-reported `w_opt` is a criterion-dependent numerical result and does not mutate the base Run or `SystemRevision`.

## Multivariate Analysis — Plan 11

Multivariate Analysis preserves ordered components, component-to-observable mappings and parameter provenance. Studio uses the public AgencityLab multivariate API and stores Lab-returned component/aggregate outputs. It does not invent an aggregate by averaging, summing, weighting or normalizing component science.

## Observable Spatial Agencity Field — Plan 12

Plan 12 introduces `OBSERVABLE_SPATIAL_FIELD` with scientific status **EXPERIMENTAL**. Its concept is exclusively:

```text
u(x,t)
  or
u(x1,x2,...,xd,t)
        ↓
public agencitylab.fields.compute_agencity_field
        ↓
beta_obs(x,t), b_obs(x,t)
```

AgencityLab applies the canonical temporal scalar pipeline locally at each spatial position. CRM remains temporal and independent for each local trajectory. Studio does not implement the local loop or equations itself.

### Exact immutable field source

A field Analysis selects one confirmed immutable NPZ `DatasetVersion`. The Run pins:

- exact DatasetVersion UUID and source SHA-256;
- exact `u` and `t` array identities/hashes;
- original N-D field shape and dtype;
- explicit normalized `time_axis`;
- ordered spatial dimensions;
- explicit coordinate arrays and their hashes, or explicit `spatial_axes=None`/sample-index mode;
- observable/time units as documented;
- exact `SystemRevision` and `ObservableDefinition`.

Shape and axis order are scientifically significant. `(time,64)` is not the same contract as `(time,8,8)`, and `(time,x,y)` is not interchangeable with `(time,y,x)`. Studio does not flatten, guess or silently reshape a field.

### Physical parameter modes

The actual AgencityLab 1.2.0 public observable-field contract supports:

```text
A_ref: scalar or exact spatial shape
tau:   scalar or exact spatial shape
w:     None, scalar or exact spatial shape
P_c:   scalar, exact spatial shape or exact space-time u.shape
```

Scalar modes use the immutable `SystemRevision` scalar. Map modes identify explicit arrays in the pinned NPZ source and freeze key, shape, dtype, unit, SHA-256, provenance and supplier in the Run snapshot. No map is derived from signal statistics.

`P_c=0` is not rejected merely because it is zero when the public Lab contract accepts it. When `w` is unspecified, Studio stores the request as `None` and transmits literal `w=None`; any effective Lab behavior is recorded separately from the requested state.

### Field execution fingerprint and Celery execution

The deterministic field fingerprint includes source SHA, field shape, time-axis identity, ordered spatial-axis metadata/hashes, parameter modes and scalar/map identities, System fingerprint, AgencityLab version, field result schema and scientific status.

```text
AnalysisRun QUEUED
  ↓ Redis: Run UUID only
worker loads immutable Run
  ↓
load exact N-D source + axes + parameter maps
  ↓ structural validation only
labbridge.fields
  ↓
public compute_agencity_field
  ↓
lossless immutable field artifact + SHA-256
  ↓
COMPLETED
```

Double delivery observes persisted state and one-to-one artifact publication. A deterministic Lab validation error becomes a safe failed Run; no completed artifact is fabricated.

### Field result artifact

The field result reuses private `AnalysisResultArtifact` with `ZIP_NPY_JSON`. N-D shapes, axis order, real/complex dtypes and values are preserved. Public `beta` and `b` are exposed in the field manifest with observable aliases `beta_obs` and `b_obs`.

Studio stores only fields that are actually present in public `ObservableAgencityFieldResult`; it does not reconstruct absent series. The public observable-field result does not expose field `theta`, so Studio does not manufacture field structural orientation from `arg(beta_obs)`.

## Autonomous Research Field — Plan 13

Plan 13 introduces `RESEARCH_FIELD` with explicit scientific status **RESEARCH**. It is not an extension of the observable field result object and does not change the canonical or Plan 12 pipeline.

```text
explicit phi initial condition
        ↓
ResearchFieldInputArtifact
        ↓
AnalysisRun(kind=RESEARCH_FIELD)
        ↓ Celery
labbridge.research
        ↓
public AgencityLab 1.2.0 autonomous solver
        ↓
DynamicalAgencityFieldSolution
        ↓
immutable AnalysisResultArtifact
```

Supported public autonomous models are `simulate_klein_gordon`, `simulate_dissipative_klein_gordon` and `simulate_tdgl`. Studio constructs public `UniformRectilinearGrid`, `QuarticAgencityPotential` and Periodic/Dirichlet/Neumann boundary objects from explicit configuration, but implements no field equation, stencil or time integrator.

### Research initial-condition sources

A Research Run can freeze an initial condition only through an implemented public contract:

- exact `phi_0` and optional `phi_dot_0` arrays from a pinned immutable NPZ DatasetVersion;
- public `domain_wall_profile` on an explicit one-dimensional Lab grid;
- public `vortex_field` with caller-supplied radial-profile array and exact two-dimensional axes;
- explicit completed Observable Field Run passed through public `agencitylab.fields.beta_to_phi`, with exact source result SHA and selected time index.

The observable bridge is user-triggered. Completing an Observable Field Run never creates a Research Run automatically. `beta_obs(x,t)` remains the EXPERIMENTAL observable field; bridge output becomes a distinct RESEARCH initial `phi` artifact. No silent identity `beta_obs = phi` exists.

For second-order dynamics an absent velocity is represented only by the explicit zero-velocity initialization convention recorded in provenance. TDGL is first-order and keeps `phi_dot` absent rather than fabricating a velocity field.

### Research geometry, boundaries and numerical method

A Run freezes:

- spatial rank and exact field shape;
- exact coordinate arrays and axis order;
- public Lab uniform-grid validation, spacing, origins and domain limits;
- boundary kind and explicit value/gradient where applicable;
- `lambda`, `mu` and required `gamma` with provenance;
- `dt_solver` and `n_steps` labelled **NUMERICAL METHOD**;
- AgencityLab/Studio/Python versions;
- immutable input SHA, execution fingerprint and result SHA.

`dt_solver` is not canonical `tau`; Research integration steps are not CRM window `w`. Studio does not resample a non-uniform Research grid or alter a scientific/model parameter for numerical convenience.

### Research coherent structures and topology

Plan 13 exposes public domain-wall/vortex helpers only as theoretical initializers. It does not implement a defect detector. A heatmap that resembles a vortex is never labelled “Vortex detected” without an explicit Lab output.

Optional autonomous topology uses public `agencitylab.fields.phase_winding` on a user-configured ordered contour. This is distinct from any temporal winding diagnostic of canonical/observable Agencity. Displayed `arg(phi)` is not automatically a topological invariant.

### Research thermodynamics

The integrated post-processing subset is public `total_dissipated_power`, `total_entropy_production` and `field_agencial_entropy`. Inputs such as `T_eff`, `gamma` and entropy coefficient `a` are explicit. Studio does not infer temperature/entropy/dissipation from noise, variance or canonical `D`.

### Gravity and other advanced layers

AgencityLab 1.2.0 publicly exposes RESEARCH gravitational primitives/residuals but explicitly provides no Einstein or metric dynamics solver. Studio 0.13 therefore exposes no executable Gravity analysis and no synthetic curvature visualization. The public effective-beta field remains a separate RESEARCH layer and is out of Plan 13 scope. Quantum is SPECULATIVE and out of scope; cosmology is out of scope.

### Research artifacts, idempotence and resource limits

The private `ResearchFieldInputArtifact` and completed result artifact are immutable `ZIP_NPY_JSON` containers using non-pickle NumPy arrays. N-D shapes and complex dtypes are preserved without silent downcasting.

Celery receives only the Run UUID. Duplicate deliveries observe persisted lifecycle state. `RESEARCH_FIELD_MAX_ELEMENTS`, `RESEARCH_FIELD_MAX_STEPS` and `RESEARCH_FIELD_MAX_OUTPUT_BYTES` are operational limits: oversized jobs are rejected, never silently shortened or downsampled scientifically.

## Permissions

Analysis permissions continue to inherit Workspace membership:

- Owner/Editor/Analyst can create, configure, run, rerun and inspect supported Analyses according to existing lifecycle policy;
- Viewer can inspect completed results;
- non-members receive object-scoped 404 responses for detail, manifest, slice, point, trace, derived-output and artifact-backed endpoints.

Plan 13 adds no “research user” ACL.

## Scientific equivalence tests

Expected scientific values come from direct AgencityLab execution, never from copied Studio equations.

Plan 12 compares direct `compute_agencity_field` with the Studio public bridge and selected local trajectories with direct canonical `compute_agencity`.

For every integrated Plan 13 module tests compare:

```text
direct public AgencityLab 1.2.0 call
==
Studio -> labbridge.research -> same public Lab call
```

This includes the autonomous solvers, explicit `beta_to_phi` bridge, coherent initializers, `phase_winding` and selected thermodynamic functions. Tests also block private Lab imports, hidden Studio numerics, complex/shape corruption and unsupported Research execution endpoints.

## Scientific hierarchy

The final hierarchy is explicit in code, UI, provenance and documentation:

```text
Canonical scalar Agencity       CANONICAL
Observable spatial Agencity     EXPERIMENTAL
Autonomous phi field            RESEARCH
Autonomous topology/thermo      RESEARCH when explicitly computed by Lab
```

`beta_obs(x,t)` and `b_obs(x,t)` are observable fields derived from `u(x,t)`. `phi(x,t)` is an autonomous Research field. Successful Research execution confirms software execution, not experimental establishment of the physical model.

See `docs/observable-spatial-fields.md` for the Plan 12 source/parameter contract, `docs/research-fields.md` for the Plan 13 capability audit and Research boundary, and `docs/visualization.md` for artifact-only presentation rules.
