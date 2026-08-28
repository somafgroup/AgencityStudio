# Analyses, derived studies and observable fields

AgencityStudio separates canonical scalar execution, diagnostic interpretation, sensitivity exploration, multivariate execution and **EXPERIMENTAL observable spatial field** execution. Studio orchestrates public AgencityLab APIs; it is not a second scientific engine.

## Scientific execution boundaries

| Workflow | Scientific status | Public AgencityLab entry point |
| --- | --- | --- |
| Canonical scalar | canonical local engine | `agencitylab.compute_agencity` |
| Diagnostics | diagnostic layer | `agencitylab.analyze_agencity` |
| Tau/window sensitivity | derived sensitivity layer | public multiscale/window APIs |
| Multivariate | public multivariate extension | public multivariate API |
| Observable spatial field | **EXPERIMENTAL** | `agencitylab.fields.compute_agencity_field` |

A completed execution means the software call and immutable publication succeeded. It does not imply coherent or “real” agencity. `beta != 0`, non-zero local `beta_obs`, high `D` or large `b_obs` are not by themselves proof of real agencity.

## Analysis and AnalysisRun

`Analysis` is a mutable Project-owned workspace. `AnalysisRun` is the immutable reproducibility boundary for an exact execution. A queued Run freezes source identity/hash, scientific mapping, exact `SystemRevision` and `ObservableDefinition`, parameter state, software versions, execution fingerprint and warnings before Celery executes the public Lab API.

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

The actual AgencityLab 1.1.3 public field contract supports:

```text
A_ref: scalar or exact spatial shape
tau:   scalar or exact spatial shape
w:     None, scalar or exact spatial shape
P_c:   scalar, exact spatial shape or exact space-time u.shape
```

Scalar modes use the immutable `SystemRevision` scalar. Map modes identify explicit arrays in the pinned NPZ source and freeze key, shape, dtype, unit, SHA-256, provenance and supplier in the Run snapshot. No map is derived from signal statistics.

`P_c=0` is not rejected merely because it is zero when the public Lab contract accepts it. When `w` is unspecified, Studio stores the request as `None` and transmits literal `w=None`; any effective Lab behavior is recorded separately from the requested state.

### Field execution fingerprint

The deterministic field fingerprint includes source SHA, field shape, time-axis identity, ordered spatial-axis metadata/hashes, parameter modes and scalar/map identities, System fingerprint, AgencityLab version, field result schema and scientific status. Two flattened-equal fields with different shapes or axis order therefore receive different contracts.

### Field Celery execution

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

The field result reuses private `AnalysisResultArtifact` with `ZIP_NPY_JSON` and a compact schema identifier compatible with the existing artifact column. N-D shapes, axis order, real/complex dtypes and values are preserved. Public `beta` and `b` are exposed in the field manifest with observable aliases `beta_obs` and `b_obs`.

Studio stores only fields that are actually present in public `ObservableAgencityFieldResult`; it does not reconstruct absent series. In AgencityLab 1.1.3 the public field result does not expose `theta`, so Plan 12 does not manufacture field structural orientation from `arg(beta_obs)`.

## Permissions

Analysis permissions continue to inherit Workspace membership:

- Owner/Editor/Analyst can create, configure, run, rerun and inspect supported Analyses according to existing lifecycle policy;
- Viewer can inspect completed results;
- non-members receive object-scoped 404 responses for detail, manifest, slice, point, trace and artifact-backed endpoints.

## Scientific equivalence tests

Canonical tests compare direct public `compute_agencity` with `labbridge.execution`. Plan 12 adds two blocking comparisons:

```text
direct compute_agencity_field
==
Studio -> labbridge.fields -> compute_agencity_field
```

and for selected spatial points:

```text
field local trajectory
==
direct public compute_agencity(local temporal series)
```

Expected scientific values come from AgencityLab direct execution, never from copied Studio equations.

## Scientific boundary of Plan 12

Plan 12 introduces no spatial CRM, neighbour-correlation CRM, spatial derivative, gradient, Laplacian, PDE, autonomous `phi`, beta-to-phi bridge, domain walls, vortices, thermodynamics, gravity, quantum or cosmological dynamics. It performs no interpolation, resampling, smoothing, filling, normalization, clipping or spatial averaging during Analysis.

`beta_obs(x,t)` and `b_obs(x,t)` are observable fields derived from measured or simulated `u(x,t)`. They are not autonomous dynamical field `phi(x,t)` and must remain labeled **EXPERIMENTAL**.

See `docs/observable-spatial-fields.md` for the exact Plan 12 source, parameter, storage and UI contract and `docs/visualization.md` for field slicing/presentation rules.
