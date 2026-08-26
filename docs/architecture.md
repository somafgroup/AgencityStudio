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

Studio is not a second scientific implementation. Canonical equations and diagnostic equations remain owned by AgencityLab.

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
              └── DiagnosticRun 1..n
                    └── DiagnosticResultArtifact
```

A `DatasetVersion`, `PreparedDataArtifact`, `SystemRevision`, `AnalysisRun` and completed `DiagnosticRun` are reproducibility boundaries. Historical scientific artifacts are not edited in place.

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

## Canonical vs diagnostic science

Canonical quantities remain exactly the quantities produced by AgencityLab's canonical pipeline. Diagnostics consume those quantities but do not redefine them.

Plan 9 therefore treats coherence, angular variance, orientation stability evidence, curvature, winding-related output, zeros, events, transitions, regime signatures/classification and real-agencity assessment as a separate layer. Their exact availability and status follow AgencityLab 1.1.3 public output.

Studio never infers:

```text
beta != 0  => real agencity
high D     => real agencity
```

Diagnostic thresholds are either part of the public Lab diagnostic contract or explicit user configuration. Studio does not silently introduce universal constants. Missing criteria may legitimately produce `undetermined`, empty or no-detection results.

## Diagnostic provenance

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

A completed run additionally pins a private immutable `DiagnosticResultArtifact` and its result SHA-256. Configuration changes create a new DiagnosticRun rather than modifying history.

## Storage policy

Long numerical series remain in private immutable artifacts rather than row-per-sample SQL tables. PostgreSQL stores identity, ownership, status, hashes, provenance, configuration and artifact references.

Canonical artifacts use `ZIP_NPY_JSON` with NumPy arrays and `allow_pickle=False`. Diagnostic artifacts use a schema-versioned private JSON-oriented ZIP representation suitable for the public Lab report, including reversible handling of non-finite diagnostic values. Pickle is not used as the scientific artifact format.

Artifacts have no public media URL. Workspace permission resolution is required for all result and visualization endpoints.

## Visualization architecture

Plan 8 canonical and Plan 9 diagnostic views reuse the same locally bundled Apache ECharts 6.1.0 scientific workspace controller.

```text
immutable artifact
    ↓ schema-aware reader/service
private Workspace-scoped JSON endpoint
    ↓
ScientificWorkspaceController
    ↓
display-only charts + exact sample inspector
```

Browser code performs presentation only. It does not calculate coherence, variance, curvature, winding, zeros, regimes or real-agencity criteria.

Display decimation is never scientific input. Every displayed point retains its original canonical sample index, and the exact inspector requests the full-resolution stored sample. Diagnostic and canonical workspaces share that index through stable `sample=` deep links.

## Celery

Canonical execution and diagnostic execution are real Celery workloads. Task submission occurs after transaction commit and payloads contain stable run identifiers rather than arbitrary scientific arrays.

`analyses.diagnostic_tasks` is explicitly registered with the Celery application because it is intentionally separate from the canonical `analyses.tasks` module. Duplicate delivery is guarded by persisted run status and one-to-one artifact publication.

Deterministic Lab validation/scientific configuration errors are not treated as endlessly retryable network incidents.

## Permissions

Permissions reuse Workspace roles; there is no diagnostic-specific ACL.

- Owner and Editor can configure/run diagnostics.
- Analyst can fully configure, run and inspect diagnostics.
- Viewer can inspect completed diagnostics but cannot create them.
- Non-members receive object-scoped 404 responses.

The same rules protect diagnostic detail, artifact-backed endpoints and visualization endpoints.

## Operational boundary

`/health/ready/` verifies service dependencies and AgencityLab runtime compatibility; it does not execute a scientific diagnostic suite.

Plan 9 adds no infrastructure service and keeps `agencitylab==1.1.3` pinned. Multiscale `tau`/`w` exploration is deliberately reserved for the later sensitivity/multiscale work and is not inferred from Plan 9 diagnostics.

See `docs/analyses.md`, `docs/visualization.md` and `docs/diagnostics.md` for the execution, presentation and diagnostic contracts.