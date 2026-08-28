# Architecture overview

AgencityStudio follows a strict dependency direction:

```text
Theory of Agencity
        ↓
AgencityLab accepted implementation
        ↓ public APIs only
AgencityStudio labbridge
        ↓
Django orchestration, provenance, storage and presentation
```

Studio is not a second scientific implementation. Canonical equations, diagnostic equations, multiscale/window algorithms, multivariate computation and observable-field computation remain owned by AgencityLab.

## Ownership graph

```text
User
  ↓ membership
Workspace
  ↓
Project
  ├── Dataset
  │     └── immutable DatasetVersion
  │            └── PreparedDataArtifact (tabular preparation path)
  ├── System
  │     └── immutable SystemRevision
  └── Analysis
        └── immutable AnalysisRun
              ├── AnalysisResultArtifact
              ├── DiagnosticRun 1..n
              │     └── DiagnosticResultArtifact
              └── SensitivityStudy 1..n
                    └── SensitivityResultArtifact
```

Plan 12 does not add a second field-data workspace. Exact N-dimensional NPZ field sources remain ordinary Project-owned immutable `DatasetVersion` records with source bytes, SHA-256 and field inspection metadata.

## Scientific execution boundaries

### Canonical scalar execution

```text
exact DatasetVersion / PreparedDataArtifact
        +
exact SystemRevision and ObservableDefinition
        ↓
AnalysisRun snapshot
        ↓ Celery
labbridge.execution
        ↓
public agencitylab.compute_agencity
        ↓
AnalysisResultArtifact (ZIP_NPY_JSON)
```

Studio preserves public Lab arrays and does not reproduce the canonical equations.

### Diagnostic execution — Plan 9

```text
completed canonical AnalysisRun
        ↓ exact canonical result + SHA
DiagnosticRun
        ↓ Celery
labbridge.diagnostics
        ↓
public agencitylab.analyze_agencity
        ↓
DiagnosticResultArtifact
```

This path does not rerun canonical computation. Stored canonical `theta` is passed explicitly; missing orientation is not reconstructed from `arg(beta)`.

### Sensitivity execution — Plan 10

```text
completed canonical AnalysisRun
        ↓ exact source + fixed context
SensitivityStudy
        ↓ Celery
labbridge.sensitivity
        ├── public compute_agencity_spectrum
        └── public optimize_agencity_window
        ↓
SensitivityResultArtifact
```

A sensitivity result never mutates its base Run or SystemRevision and never automatically promotes a numerical maximum/optimum into a physical parameter.

### Multivariate execution — Plan 11

Multivariate Analyses reuse `Analysis` / `AnalysisRun`, freeze ordered component mappings and call only the public AgencityLab multivariate API. Component order is part of the immutable contract. Studio stores the Lab-returned aggregate and does not invent a second aggregation formula.

### Observable spatial field execution — Plan 12

Plan 12 is the first **EXPERIMENTAL** spatial extension:

```text
immutable NPZ DatasetVersion
   ├── exact u N-D array
   ├── exact t vector
   ├── optional explicit spatial coordinate arrays
   └── optional explicit physical parameter maps
        +
exact SystemRevision / ObservableDefinition
        ↓
AnalysisRun field snapshot
        ↓ Celery (Run UUID only)
analyses.field_tasks
        ↓
labbridge.fields
        ↓
public agencitylab.fields.compute_agencity_field
        ↓
ObservableAgencityFieldResult
        ↓
AnalysisResultArtifact (ZIP_NPY_JSON, N-D preserved)
```

The conceptual calculation is `u(x,t) -> beta_obs(x,t), b_obs(x,t)` by applying the canonical temporal scalar pipeline locally at each spatial position. AgencityLab owns that orchestration. Studio contains no spatial loop that recalculates `J`, `U`, `beta`, `b`, CRM or another Agencity quantity.

CRM remains temporal and independent at each spatial location. Plan 12 introduces no spatial CRM, neighbour correlation, spatial derivative, PDE or autonomous `phi` dynamics.

## Field source architecture

The existing tabular import path cannot faithfully encode arbitrary `(time,x,y,...)` fields without flattening. Plan 12 therefore adds NPZ as a minimal explicit N-D source format while preserving the existing ownership chain.

NPZ inspection is structural and safety-oriented:

- exact original bytes and source SHA-256 are immutable;
- NPY headers are inspected before large allocations;
- array key, shape, dtype, element count and per-member SHA-256 are recorded;
- object dtype / pickle-dependent arrays are rejected;
- unsafe ZIP member paths are rejected;
- compressed/uncompressed/element/array-count limits are operational guards;
- no interpolation, normalization, resampling, smoothing or scientific inference occurs during import.

`time_axis` is explicit. Spatial coordinate arrays are explicit when available; otherwise Studio records sample-index mode corresponding to public `spatial_axes=None`. Axis order and N-D shape are part of the Run fingerprint.

## Field physical parameters

The public AgencityLab 1.1.3 field contract supports scalar or exact spatial maps for `A_ref` and `tau`; `w=None`, scalar or exact spatial map; and scalar/spatial/exact-space-time `P_c`.

Scalar values remain `SystemRevision` context. Maps remain immutable array artifacts in the pinned source and are referenced by key/hash/provenance rather than one SQL row per cell. Studio never estimates a map from signal statistics. `w=None` remains a literal public-API request; any effective resolution is Lab-owned result context.

## Storage policy

PostgreSQL stores identity, ownership, lifecycle state, hashes, fingerprints, mapping/configuration snapshots and artifact references. Large numerical arrays do not become row-per-sample or row-per-cell tables.

Canonical, sensitivity and observable-field numerical artifacts use private `ZIP_NPY_JSON` with NumPy arrays and `allow_pickle=False`. Field serialization preserves exact N-D shape, dtype, complex values and axis order. Public field `beta`/`b` are identified with `beta_obs`/`b_obs` aliases to maintain the observable-field distinction.

The compact field schema identifier fits the existing `AnalysisResultArtifact.schema_version` storage contract. Schema semantics are carried by the manifest and versioned reader; a schema change must remain backward-aware.

Artifacts have no public media URL. Workspace permission resolution is required for all result endpoints.

## Visualization architecture

All scientific charts use locally bundled Apache ECharts 6.1.0.

```text
immutable artifact
    ↓ schema-aware reader
private Workspace-scoped endpoint
    ↓
scoped browser controller
    ↓
display-only chart + exact inspector/table/trace
```

For Plan 12, the server exposes exact manifest, time-slice/spatial-slice, exact-point and local-trace endpoints. The browser does not receive an entire large N-D field by default. One-dimensional space can render a time-space heatmap; two-dimensional space renders a selected-time map; higher dimensions use explicit slicing with fixed indices.

Display-only reduction never changes the scientific artifact. Exact selected cells and traces always use full-resolution stored data. No browser interpolation, spatial averaging, projection, PCA, gradient or Laplacian is treated as scientific output.

Complex `beta_obs` and `b_obs` may be displayed as real, imaginary, magnitude or phase representations only. In AgencityLab 1.1.3 the public observable-field result does not expose field `theta`, so Studio does not substitute `arg(beta_obs)` for structural orientation.

## Celery and idempotence

Canonical, diagnostic, sensitivity, multivariate and observable-field execution are real Celery workloads. Transaction commit occurs before enqueue. Scientific arrays are not sent through Redis; stable record UUIDs are sent instead.

Workers reload immutable snapshots and source artifacts, verify hashes/structure, call the public Lab boundary, serialize results and publish one authoritative immutable artifact. Duplicate delivery observes persisted lifecycle state and one-to-one artifact constraints.

Deterministic Lab validation/configuration errors become safe failed records; they are not endlessly retried or “fixed” by modifying physical parameters.

## Permissions

Permissions reuse Workspace/Analysis roles. Owner, Editor and Analyst can perform scientific authoring according to the existing Analysis policy; Viewer is read-only; non-members receive object-scoped 404 responses. Plan 12 adds no independent field ACL.

The same protection applies to field detail, manifest, slice, point, trace and artifact-backed routes.

## Scientific status boundary

Plan 12 must always remain distinguishable from future research field models:

```text
Observable spatial field   EXPERIMENTAL
Autonomous dynamical phi   RESEARCH (future/separate)
Thermodynamics             RESEARCH (future/separate)
Gravity                    RESEARCH (future/separate)
```

`beta_obs(x,t)` and `b_obs(x,t)` are observable fields derived from `u(x,t)`. They are not the autonomous dynamical field `phi(x,t)`. Plan 12 introduces no beta-to-phi bridge, domain wall/vortex physics, thermodynamics, gravity, quantum or cosmological execution.

## Operational boundary

`/health/ready/` verifies PostgreSQL, Redis and compatible AgencityLab availability. It does not execute `compute_agencity_field` or any scientific suite.

See `docs/analyses.md`, `docs/visualization.md`, `docs/development.md`, `docs/testing.md`, `docs/systems.md` and `docs/observable-spatial-fields.md` for detailed contracts.
