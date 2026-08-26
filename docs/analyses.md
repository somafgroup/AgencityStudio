# Analyses and DiagnosticRuns

AgencityStudio separates **canonical execution** from **diagnostic interpretation**.

Plan 7 executes the canonical scalar pipeline through AgencityLab 1.1.3. Plan 8 reads and visualizes the immutable canonical result. Plan 9 adds immutable diagnostics downstream of that result without changing canonical quantities.

## Scientific boundary

Canonical execution uses the public package-root `compute_agencity`. Studio does not reproduce equations for `u_star`, `X_star`, `A_star`, `M`, `O`, `D`, `S`, `J`, `Theta`, `U`, `beta` or `b`.

Diagnostic execution uses the public package-root `analyze_agencity`. Studio does not reproduce coherence, angular-variance, curvature, winding, zero/event, transition, regime or real-agencity equations.

A completed canonical Run means the software calculation and immutable publication succeeded. It does not imply coherence or real agencity. Likewise, `beta != 0` and high `D` are never used as proof of real agencity.

## Analysis and AnalysisRun

`Analysis` is a mutable Project-owned workspace. `AnalysisRun` is its immutable canonical reproducibility boundary.

Each queued AnalysisRun freezes:

- exact DatasetVersion or PreparedDataArtifact identity and SHA-256;
- explicit coordinate/observable column positions;
- exact SystemRevision and ObservableDefinition;
- `A_ref`, `tau`, requested `w` and `P_c` snapshots;
- public canonical options;
- AgencityLab, Studio and Python versions;
- deterministic canonical execution fingerprint.

Exactly one source is allowed and historical sources are protected from normal cascading deletion.

## Canonical parameters

`A_ref` and `tau` must be explicit positive physical/contextual values. `P_c` is explicit non-negative and `P_c = 0` is valid. `w` remains either explicit or unspecified.

When `w` is unspecified, Studio passes `None` to AgencityLab; it does not replace it with `tau`. The effective Lab result memory window may be recorded separately from the requested provenance state.

No physical parameter is derived from signal statistics.

## Canonical result artifact

Completed AnalysisRuns publish one private `AnalysisResultArtifact` using `ZIP_NPY_JSON` schema 1. Stored public canonical series include, when available:

`xi`, `u`, `u_star`, `X_star`, `A_star`, `t_star`, `M`, `O`, `D`, `S`, `J`, `theta`, `U`, `beta`, `b`.

NumPy dtypes, including complex arrays, are preserved and pickle is disabled. `execution_fingerprint` identifies the frozen computation contract; `result_sha256` identifies the exact serialized bytes.

## DiagnosticRun — Plan 9

A completed canonical AnalysisRun may own multiple immutable `DiagnosticRun` records:

```text
Analysis
  ↓
AnalysisRun
  ├── canonical AnalysisResultArtifact
  ├── DiagnosticRun 1
  ├── DiagnosticRun 2
  └── ...
```

Multiple diagnostic runs are intentional because diagnostic configuration can change without changing the canonical result.

Each DiagnosticRun pins:

- exact parent AnalysisRun;
- canonical result SHA-256;
- AgencityLab version;
- Studio/Python versions;
- public diagnostic API identifiers;
- normalized diagnostic configuration and thresholds;
- diagnostic schema version;
- deterministic diagnostic execution fingerprint;
- creator and timestamps.

A completed DiagnosticRun additionally pins its private `DiagnosticResultArtifact` and result SHA-256. Editing a threshold creates another run; it does not rewrite the old one.

## Diagnostic input contract

Plan 9 does not rerun canonical computation. The worker reads the exact immutable canonical artifact and reconstructs only the **public `AgencityResult` container** expected by the public diagnostic API.

Stored canonical `theta` is mandatory and passed explicitly. Studio never substitutes `np.angle(beta)` or a browser-computed phase. If a historical artifact lacks the required public input series, the diagnostic run is unavailable/failed safely rather than scientifically repaired.

The worker verifies the canonical result SHA before diagnostic execution so a DiagnosticRun cannot silently consume another result.

## Public diagnostic bundle in AgencityLab 1.1.3

Plan 9 uses `agencitylab.analyze_agencity` as the standard public bundle. Its result can expose, according to the Lab 1.1.3 contract:

- structural orientation `Sigma_Theta` and coherence information;
- contextual real-agencity assessment/evidence;
- beta-trajectory geometry and curvature;
- net structural-orientation turns and winding-related output under its closure contract;
- exact zero reporting;
- `D = S` critical-surface transitions;
- configurable Theta jumps;
- public D-peak detection;
- configurable structural S plateaus;
- threshold-free regime signature;
- contextual regime classification.

Legacy `b` heuristics are not promoted into the standard Studio diagnostic layer. Optional filtered peak detection that would require a new SciPy dependency is not added merely for convenience. Multiscale `tau`/`w` exploration is reserved for later work.

## Thresholds and negative outcomes

Studio defines no universal interpretive threshold. Where Lab permits contextual thresholds, the user may explicitly configure them and the exact values are persisted and transmitted unchanged.

If required criteria are absent, Lab may return `undetermined` or not-configured output. This is preserved. No detected event, empty segments, unknown regime or no diagnostic evidence is a valid software result.

A DiagnosticRun lifecycle status (`QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`) describes execution only; it is never a hidden scientific verdict.

## Celery

Canonical and diagnostic workloads use Celery after transaction commit.

Diagnostic flow:

```text
DiagnosticRun QUEUED
  ↓ Redis/Celery
analyses.diagnostic_tasks
  ↓
labbridge.diagnostics
  ↓
public agencitylab.analyze_agencity
  ↓
private DiagnosticResultArtifact
  ↓
COMPLETED
```

Duplicate delivery sees persisted run state and cannot publish two completed artifacts. Deterministic Lab validation errors are not blindly retried.

## Permissions

Analysis/diagnostic access reuses Workspace membership:

- Owner: view/configure/run/rerun/inspect plus normal lifecycle privileges;
- Editor: view/configure/run/rerun/inspect;
- Analyst: view/configure/run/rerun/inspect;
- Viewer: inspect completed canonical and diagnostic results only;
- Non-member: object endpoints resolve as 404.

Artifacts have no public media URLs.

## Scientific equivalence

Canonical tests compare direct `compute_agencity` with `labbridge.execution` on the same inputs.

Diagnostic tests compare direct public `analyze_agencity` with `labbridge.diagnostics` using the same public rehydrated result and configuration. Studio never derives expected diagnostic values from copied formulas.

The stored-Theta regression explicitly protects a case where canonical `Theta` differs from `arg(beta)`.

## Visualization relationship

Plan 8 canonical visualization reads `AnalysisResultArtifact`. Plan 9 diagnostic visualization reads `DiagnosticResultArtifact` plus the exact canonical coordinate/index relation. Neither visualization path performs scientific computation.

Display decimation never changes diagnostic calculation input. Exact sample synchronization uses original canonical sample indices.

See `docs/visualization.md` and `docs/diagnostics.md` for presentation and diagnostic details.