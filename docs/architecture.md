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

Studio is not a second scientific implementation. Canonical equations, diagnostic equations and multiscale/window scientific algorithms remain owned by AgencityLab.

## Ownership graph

```text
User
  ↓ membership
Workspace
  ↓
Project
  ├── Dataset
  │     └── DatasetVersion
  │            └── PreparedDataArtifact
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

A `DatasetVersion`, `PreparedDataArtifact`, `SystemRevision`, `AnalysisRun`, completed `DiagnosticRun` and completed `SensitivityStudy` are reproducibility boundaries. Historical scientific artifacts are not edited in place.

## Scientific execution boundaries

### Canonical execution

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

The canonical result contains the AgencityLab outputs such as `xi`, `u`, `u_star`, `X_star`, `A_star`, `M`, `O`, `D`, `S`, `J`, canonical `theta`, `U`, `beta` and `b` when present. Studio preserves their numeric representation; it does not reproduce their equations.

### Diagnostic execution — Plan 9

```text
completed AnalysisRun
        ↓
exact AnalysisResultArtifact + canonical result SHA-256
        ↓
DiagnosticRun snapshot
        ↓ Celery
labbridge.diagnostics
        ↓
public AgencityResult container rehydrated from stored canonical arrays
        ↓
public agencitylab.analyze_agencity
        ↓
DiagnosticResultArtifact (private ZIP_JSON)
```

This path does **not** rerun `compute_agencity`. The public `AgencityResult` container is populated from the immutable stored canonical arrays and the stored canonical `theta` is passed explicitly. An artifact without the required stored `theta` is not repaired with `arg(beta)`.

A DiagnosticRun never mutates its parent AnalysisRun, canonical artifact, canonical result SHA-256 or canonical execution fingerprint.

### Sensitivity execution — Plan 10

```text
completed AnalysisRun
        ↓
exact source + canonical result/source hashes + fixed parameter snapshot
        ↓
SensitivityStudy snapshot
        ↓ Celery
labbridge.sensitivity
        ├── public agencitylab.api.compute_agencity_spectrum
        └── public agencitylab.api.optimize_agencity_window
        ↓
SensitivityResultArtifact (private ZIP_NPY_JSON)
```

A `TAU_MULTISCALE` study varies only an explicit `tau` grid. If the base Run requested `w` as unspecified, Studio passes `windows=None`; AgencityLab applies and returns its documented effective-window behavior. If the base `w` was explicit, that scalar is kept fixed across the `tau` sweep.

A `W_SENSITIVITY` study varies only explicit CRM-window candidates while keeping base `tau`, `A_ref`, `P_c`, source, mapping and `SystemRevision` fixed. Studio prevalidates the candidates against the discrete sampling contract rather than letting an incompatible `w` be silently rounded.

The Lab-returned `w_opt` is preserved as a numerical optimum under the public Phi2 criterion. It is not promoted into the System or canonical Run. Likewise Studio performs no `argmax`/peak rule to reinterpret a multiscale maximum as physical `tau`.

## Canonical vs diagnostic vs sensitivity science

Canonical quantities remain exactly the quantities produced by AgencityLab's canonical pipeline. Diagnostics consume those quantities but do not redefine them. Sensitivity studies compare explicitly requested scale/window configurations and do not redefine physical parameters.

Plan 9 therefore treats coherence, angular variance, orientation stability evidence, curvature, winding-related output, zeros, events, transitions, regime signatures/classification and real-agencity assessment as a separate layer. Their exact availability and status follow AgencityLab 1.1.3 public output.

Plan 10 keeps `dt`, `tau` and `w` distinct. `dt` describes acquisition/sampling; `tau` is physical/contextual structural time; `w` is CRM memory window. Neither a multiscale maximum nor a criterion-specific window optimum is automatically a physical parameter estimate.

Studio never infers:

```text
beta != 0       => real agencity
high D          => real agencity
spectrum maximum => physical tau
Phi2 optimum     => physical w
```

Diagnostic thresholds are either part of the public Lab diagnostic contract or explicit user configuration. Sensitivity grids are explicit user configuration. Studio does not silently introduce universal constants or data-derived physical parameters.

## Derived-study provenance

A `DiagnosticRun` pins at least:

- exact `AnalysisRun`;
- canonical result SHA-256;
- AgencityLab version;
- Studio/Python versions;
- diagnostic public API identifiers;
- normalized diagnostic configuration;
- threshold values or explicit absence/default state;
- deterministic diagnostic execution fingerprint;
- warnings and lifecycle status.

A `SensitivityStudy` pins at least:

- exact `AnalysisRun`;
- canonical result SHA-256 and source SHA-256;
- exact `SystemRevision` and system fingerprint;
- mapping and fixed parameter snapshots;
- study type, grid type/unit and exact requested values;
- requested `w` mode and fixed/varied semantics;
- public Lab API identifier;
- AgencityLab/Studio/Python versions;
- deterministic execution fingerprint;
- warnings and lifecycle status.

Completed studies additionally pin private immutable result artifacts and result SHA-256 values. Configuration changes create new historical records rather than modifying old ones.

## Storage policy

Long numerical series and multiscale matrices remain in private immutable artifacts rather than row-per-sample SQL tables. PostgreSQL stores identity, ownership, status, hashes, provenance, configuration and artifact references.

Canonical and sensitivity artifacts use `ZIP_NPY_JSON` with NumPy arrays and `allow_pickle=False`. Diagnostic artifacts use a schema-versioned private JSON-oriented ZIP representation suitable for the public Lab report, including reversible handling of non-finite diagnostic values. Pickle is not used as the scientific artifact format.

Sensitivity artifacts preserve Lab-returned complex multiscale `b` and `beta` arrays with their NumPy dtype. The table/readers retain exact values; chart-only magnitude representations do not rewrite storage.

Artifacts have no public media URL. Workspace permission resolution is required for all result and visualization endpoints.

## Visualization architecture

Plan 8 canonical, Plan 9 diagnostic and Plan 10 sensitivity views reuse locally bundled Apache ECharts 6.1.0.

```text
immutable artifact
    ↓ schema-aware reader/service
private Workspace-scoped JSON endpoint
    ↓
scoped scientific/sensitivity controller
    ↓
display-only charts + exact table/inspector
```

Browser code performs presentation only. It does not calculate canonical quantities, diagnostics, multiscale optima or physical-parameter estimates.

Display decimation is never scientific input. Canonical and diagnostic workspaces preserve canonical sample indices. Sensitivity plots use the exact Lab-returned scale order and an exact table alternative.

## Celery

Canonical execution, diagnostic execution and sensitivity execution are real Celery workloads. Task submission occurs after transaction commit and payloads contain stable run/study identifiers rather than scientific arrays.

`analyses.diagnostic_tasks` is explicitly registered with the Celery application because it is intentionally separate from the canonical `analyses.tasks` module. The standard `sensitivity.tasks` module is discovered through the installed Django app. Duplicate delivery is guarded by persisted lifecycle state and one-to-one artifact publication.

Deterministic Lab validation/scientific configuration errors are not treated as endlessly retryable network incidents.

## Permissions

Permissions reuse Workspace/Analysis roles; there is no separate diagnostic or sensitivity ACL.

- Owner and Editor can configure/run derived studies.
- Analyst can fully configure, run and inspect derived studies.
- Viewer can inspect completed derived studies but cannot create them.
- Non-members receive object-scoped 404 responses.

The same rules protect detail, artifact-backed and visualization endpoints.

## Operational boundary

`/health/ready/` verifies service dependencies and AgencityLab runtime compatibility; it does not execute a diagnostic or multiscale suite.

Plan 10 adds no infrastructure service and keeps `agencitylab==1.1.3` pinned. It does not begin multivariate, field, batch, fitting or automatic calibration work.

See `docs/analyses.md`, `docs/visualization.md`, `docs/diagnostics.md` and `docs/sensitivity-and-multiscale.md` for the canonical, presentation, diagnostic and scale/window contracts.
