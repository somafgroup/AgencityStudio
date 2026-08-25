# Canonical Analyses

Plan 7 introduces the first AgencityStudio workflow that actually executes the canonical scalar pipeline through **AgencityLab 1.1.3**.

## Scientific boundary

AgencityStudio is an orchestration, provenance, storage, permissions, and user-interface layer. It is **not** a second implementation of AgencityLab.

All canonical Agencity quantities are computed by AgencityLab through the public package-root function `compute_agencity`. Studio does not contain or reproduce the equations for `u_star`, `X_star`, `A_star`, `M`, `O`, `D`, `S`, `J`, `Theta`, `U`, `beta`, or `b`.

Analysis execution never sorts, resamples, interpolates, filters, fills, smooths, normalizes, standardizes, or otherwise repairs the selected data. If such preparation is required, it must already exist as an explicit `PreparedDataArtifact` created through the Data Preparation workflow.

Plan 7 also does not calculate or interpret coherence, angular variance, curvature, winding, events, transitions, regimes, or “real agencity”. A `COMPLETED` Run only means that the canonical software execution and immutable result publication completed successfully.

## Analysis vs AnalysisRun

`Analysis` is a mutable, Project-owned user workspace. It has a stable UUID, a name, description, the currently configured source/mapping/System selection, and an `ACTIVE` or `ARCHIVED` lifecycle.

`AnalysisRun` is the immutable reproducibility boundary. Every queued Run freezes:

- the exact source type and source UUID;
- the exact source SHA-256;
- raw DatasetVersion or PreparedDataArtifact identity;
- Prepared Data lineage when applicable;
- coordinate and observable column positions and metadata;
- exact `SystemRevision` and selected `ObservableDefinition`;
- System configuration fingerprint;
- `A_ref`, `tau`, requested `w`, and `P_c`, with origin and justification snapshots;
- public `compute_agencity` options used by Studio;
- AgencityLab, Studio, and Python versions;
- deterministic execution fingerprint.

Run numbering is unique per Analysis and allocated while the Analysis row is locked, so concurrent creation cannot deliberately reuse a run number.

## Source pinning

Exactly one source is allowed:

- `DatasetVersion` (`RAW_DATASET_VERSION`), or
- `PreparedDataArtifact` (`PREPARED_DATA`).

The database enforces this with an exactly-one-source check constraint. Both foreign keys use `PROTECT` from AnalysisRun, so a source used for reproducibility cannot later disappear through normal cascading deletion.

Only `READY` sources are accepted. Studio reads the exact immutable bytes and extracts only the two explicitly mapped columns by one-based position. Duplicate-looking column names are therefore not ambiguous.

## Observable mapping

Canonical scalar execution requires an explicit coordinate/time column and observable column. Dataset annotations may be useful to the user, but Studio does not silently auto-map a Run. Review displays the selected source column position, name, unit, and the exact System observable UUID/name represented by the mapping snapshot.

## Physical/contextual parameters

Plan 7 uses the values documented by the selected immutable `SystemRevision`:

- `A_ref` must be explicit and positive;
- `tau` must be explicit and positive;
- `P_c` must be explicit and non-negative; `P_c = 0` is valid;
- `w` remains either `EXPLICIT` or `UNSPECIFIED`.

When `w` is `UNSPECIFIED`, Studio passes `w=None` to the public AgencityLab API. Studio does **not** set `w=tau`. AgencityLab 1.1.3 currently applies its documented omitted-window convention internally and exposes the effective value as result metadata. Studio records that returned value separately as `effective_w` while keeping the requested state `UNSPECIFIED`.

Plan 7 intentionally does not provide Analysis-level physical-parameter overrides. This keeps the initial canonical execution path unambiguous: the parameter snapshot is the SystemRevision contract. Explicit, justified overrides can be introduced later if there is a concrete workflow that warrants a second provenance layer.

No parameter is derived automatically from signal statistics.

## Units

AgencityLab 1.1.3 treats unit strings as descriptive metadata and performs no implicit numerical conversion. Plan 7 therefore uses the conservative **Strategy A**:

- the observable source values must already be expressed in the same unit label as the System observable and `A_ref`;
- the coordinate values must already use the same unit label as `tau` and explicit `w`;
- `P_c` keeps its System unit;
- dimensionally compatible but differently scaled labels such as `km/h` and `m/s` are not silently converted.

If conversion is required, create an explicit Prepared Data artifact first. Recognized incompatible dimensions are blocking errors. Matching unknown unit labels can be retained with a warning because Studio cannot dimensionally verify them.

Datetime coordinates are not automatically converted to elapsed numerical coordinates in Plan 7. The public scalar API expects numeric coordinates.

## Structural preflight and Lab authority

Studio performs structural checks that do not reproduce Agencity equations: source readiness, mapped columns, numeric/finite samples, strictly increasing coordinates, uniform sampling, and the AgencityLab 1.1.3 CRM window/sampling contract. Numerical tolerances used to recognize uniform sampling or exact window multiples exist only to account for floating-point representation.

The worker still treats AgencityLab as final authority. Public Lab validation failures are recorded as `LAB_VALIDATION_ERROR`; other public Lab failures are `LAB_EXECUTION_ERROR`. Studio source/storage/internal failures use separate lightweight categories. Raw tracebacks are logged server-side, not presented to users.

Deterministic scientific validation failures are not automatically retried.

## Celery execution

A Run is created in `QUEUED` before Celery submission. Submission happens from `transaction.on_commit()` and the broker payload contains only the Run UUID.

The worker:

1. locks and claims the Run (`QUEUED -> RUNNING`);
2. reloads the pinned source;
3. materializes the exact mapped `xi` and `u` arrays without modification;
4. loads the frozen parameter/options snapshots;
5. calls `labbridge.execute_canonical_analysis`;
6. serializes the public result;
7. atomically publishes a private result artifact;
8. creates result metadata and marks the Run `COMPLETED` in one transaction.

Duplicate task delivery sees the guarded Run state and does not publish a second artifact. Queued Runs can be cancelled. Once a Run is `RUNNING`, Studio does not pretend that a non-cooperative AgencityLab call can be interrupted instantly.

## Result storage

Numerical result series are not stored one-row-per-sample in PostgreSQL. Each completed Run has one private `AnalysisResultArtifact`.

Current format: `ZIP_NPY_JSON`, Studio result schema version `1`.

The ZIP contains:

- `manifest.json` with result schema, public series inventory, shape, dtype, units, software versions, Run identity, source hash, System revision/fingerprint, execution fingerprint, and public Lab metadata;
- `.npy` payloads for each public canonical series used by Plan 7.

The result inventory is based on the real AgencityLab 1.1.3 public result contract: `xi`, `u`, `u_star`, `X_star`, `A_star`, `t_star`, `M`, `O`, `D`, `S`, `J`, `theta`, `U`, `beta`, and `b` when present.

NumPy dtypes are preserved. Complex arrays `U`, `beta`, and `b` are not converted to strings, split into lossy representations, or downcast. `allow_pickle=False` is used for result reading/writing.

Publication uses a sibling temporary file followed by an atomic filesystem replace on the shared private web/worker storage volume. The artifact SHA-256 is computed from the exact final serialized bytes.

`execution_fingerprint` identifies the frozen execution contract. `result_sha256` identifies the serialized result bytes. They are intentionally different concepts.

## Permissions

Analysis access reuses Workspace/Project membership; there is no additional ACL.

- Owner: view, create, configure, run, inspect results, archive/restore, hard-delete an Analysis when no Run is queued/running.
- Editor: view, create, configure, run, inspect results, archive/restore; no hard delete.
- Analyst: view, create, configure, run, inspect results; no destructive Analysis lifecycle operations.
- Viewer: view Analysis and completed Run/result metadata only.
- Non-member: object endpoints resolve as 404.

Result files never have a public media URL. Views expose result metadata only after normal object permission resolution.

## Scientific equivalence

The fundamental Plan 7 regression test compares:

```python
from agencitylab import compute_agencity

# direct
direct = compute_agencity(...)

# Studio integration boundary
through_studio = execute_canonical_analysis(...).result
```

Public result arrays are compared directly using strict floating-point tolerances. Studio does not reconstruct expected canonical values from copied equations. Representative tests cover deterministic sinusoidal input, constant signal, `P_c = 0`, and the public unspecified-`w` contract.

The end-to-end worker integration additionally reloads the private stored result and compares its canonical arrays to a direct AgencityLab computation for the same pinned source and parameters.

## Deliberately deferred

Plan 7 does not implement:

- interactive synchronized scientific plots or complex-plane workspaces (Plan 8);
- coherence, angular variance, curvature, winding, events, transitions, regime classification, or real-agencity diagnostics;
- multivariate, field, batch, spectrum, thermodynamic, quantum, gravitational, or cosmological workflows;
- full user-facing result export;
- automatic parameter inference;
- Analysis-level physical parameter overrides;
- automatic preprocessing or unit conversion during canonical execution.
