# Analyses, DiagnosticRuns and SensitivityStudies

AgencityStudio separates **canonical execution**, **diagnostic interpretation** and **sensitivity exploration**.

Plan 7 executes the canonical scalar pipeline through AgencityLab 1.1.3. Plan 8 reads and visualizes the immutable canonical result. Plan 9 adds immutable diagnostics downstream of that result. Plan 10 adds immutable tau/window sensitivity studies without changing the canonical Run or SystemRevision.

## Scientific boundary

Canonical execution uses public `compute_agencity`. Studio does not reproduce equations for `u_star`, `X_star`, `A_star`, `M`, `O`, `D`, `S`, `J`, `Theta`, `U`, `beta` or `b`.

Diagnostic execution uses public `analyze_agencity`. Studio does not reproduce coherence, angular-variance, curvature, winding, zero/event, transition, regime or real-agencity equations.

Sensitivity execution uses public `agencitylab.api.compute_agencity_spectrum` and `agencitylab.api.optimize_agencity_window`. Studio does not reproduce multiscale or CRM-window optimization algorithms and does not turn a numerical maximum into a physical-parameter estimate.

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

No physical parameter is derived from signal statistics. `dt`, `tau` and `w` remain scientifically distinct.

## Canonical result artifact

Completed AnalysisRuns publish one private `AnalysisResultArtifact` using `ZIP_NPY_JSON` schema 1. Stored public canonical series include, when available:

`xi`, `u`, `u_star`, `X_star`, `A_star`, `t_star`, `M`, `O`, `D`, `S`, `J`, `theta`, `U`, `beta`, `b`.

NumPy dtypes, including complex arrays, are preserved and pickle is disabled. `execution_fingerprint` identifies the frozen computation contract; `result_sha256` identifies the exact serialized bytes.

## Derived immutable studies

A completed AnalysisRun can own multiple independent derived records:

```text
Analysis
  ↓
AnalysisRun
  ├── canonical AnalysisResultArtifact
  ├── DiagnosticRun 1..n
  │     └── DiagnosticResultArtifact
  └── SensitivityStudy 1..n
        └── SensitivityResultArtifact
```

Neither child path mutates the canonical parent.

## DiagnosticRun — Plan 9

Multiple diagnostic runs are intentional because diagnostic configuration can change without changing the canonical result.

Each DiagnosticRun pins the exact parent AnalysisRun, canonical result SHA-256, software versions, public diagnostic API identifiers, normalized configuration/thresholds, deterministic diagnostic fingerprint and creator/timestamps. A completed run additionally pins its private result artifact and SHA-256.

Plan 9 does not rerun canonical computation. The worker reads the exact immutable canonical artifact and reconstructs only the **public `AgencityResult` container** expected by the public diagnostic API. Stored canonical `theta` is mandatory and passed explicitly. Studio never substitutes `np.angle(beta)`.

The public Lab 1.1.3 diagnostic bundle can expose structural-orientation/coherence information, contextual real-agencity assessment, geometry/curvature, winding-related output, zeros, transitions, D peaks, S plateaus, regime signatures and contextual classification. Legacy heuristics are not promoted silently.

## SensitivityStudy — Plan 10

A `SensitivityStudy` is an immutable derived study pinned to one completed AnalysisRun. It records:

- canonical Run ID and canonical result SHA-256;
- source SHA-256;
- exact SystemRevision and system fingerprint;
- mapping snapshot;
- fixed `A_ref`, `P_c`, base `tau` and requested base `w` snapshots;
- study type;
- exact scale grid and grid-generation method;
- grid unit;
- fixed/varied semantics;
- public Lab API identifier;
- AgencityLab/Studio/Python versions;
- deterministic study fingerprint;
- warnings/lifecycle;
- completed result artifact SHA-256.

Changing the grid creates another study. A completed/failed/cancelled historical study is immutable.

### `TAU_MULTISCALE`

The study sends an explicit tau grid to:

```python
agencitylab.api.compute_agencity_spectrum
```

`A_ref`, `P_c`, source, mapping and SystemRevision remain fixed.

If the base Run requested `w` as unspecified, Studio sends `windows=None`. It does not materialize `w=tau_i`. Lab 1.1.3 returns effective `w` per scale and Studio records/displays those values separately.

If base `w` is explicit, Studio passes that one explicit scalar to the spectrum API, so `w` remains fixed while tau varies.

A numerical maximum is not automatically the physical `tau`; Studio does not perform peak/argmax promotion.

### `W_SENSITIVITY`

The study sends exact explicit candidate windows to:

```python
agencitylab.api.optimize_agencity_window
```

Base `tau`, `A_ref`, `P_c`, source, mapping and SystemRevision remain fixed. Candidate windows are prevalidated against the canonical `w/dt` sampling contract so Studio does not silently depend on candidate rounding.

Lab returns the Chapter-13 `Phi2` criterion outputs and `w_opt`. Studio stores and displays that result as a **Lab-reported numerical optimum under Phi2**. It does not write `w_opt` into the SystemRevision or AnalysisRun.

## Thresholds, grids and negative outcomes

Studio defines no universal interpretive threshold. Diagnostic thresholds follow Lab/user configuration. Sensitivity grids are explicit study configuration, not theory constants or estimators.

If required diagnostic criteria are absent, Lab may return `undetermined`. A sensitivity result may be flat or unexpected. These are valid software/scientific outputs; they are not reasons to alter parameters or theory.

Lifecycle statuses (`QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`) describe execution only.

## Celery

Canonical, diagnostic and sensitivity workloads use Celery after transaction commit. Redis receives stable UUID identifiers rather than scientific arrays.

Sensitivity flow:

```text
SensitivityStudy QUEUED
  ↓ Redis/Celery
sensitivity.tasks
  ↓
labbridge.sensitivity
  ↓
public AgencityLab multiscale/window API
  ↓
private SensitivityResultArtifact
  ↓
COMPLETED
```

Duplicate delivery sees persisted state and cannot publish two authoritative artifacts. Deterministic Lab validation errors are not blindly retried.

## Permissions

Access reuses Workspace membership:

- Owner: view/configure/run/rerun/inspect plus normal lifecycle privileges;
- Editor: view/configure/run/rerun/inspect;
- Analyst: view/configure/run/rerun/inspect;
- Viewer: inspect completed canonical/diagnostic/sensitivity results only;
- Non-member: object endpoints resolve as 404.

Artifacts have no public media URLs.

## Scientific equivalence

Canonical tests compare direct `compute_agencity` with `labbridge.execution`.

Diagnostic tests compare direct public `analyze_agencity` with `labbridge.diagnostics` on the same public diagnostic input.

Sensitivity tests compare direct public `compute_agencity_spectrum` and `optimize_agencity_window` with `labbridge.sensitivity` on identical arrays, physical/contextual inputs and candidate grids. Studio never derives expected scientific values from copied formulas.

## Visualization relationship

Plan 8 canonical visualization reads `AnalysisResultArtifact`. Plan 9 diagnostic visualization reads `DiagnosticResultArtifact` plus canonical sample indices. Plan 10 sensitivity visualization reads `SensitivityResultArtifact` and uses tau/w as the scale axis rather than the signal coordinate.

All chart derivations are presentation-only. Exact artifacts/tables remain authoritative and no chart selection mutates scientific history.

See `docs/visualization.md`, `docs/diagnostics.md` and `docs/sensitivity-and-multiscale.md` for detailed presentation and derived-study contracts.
