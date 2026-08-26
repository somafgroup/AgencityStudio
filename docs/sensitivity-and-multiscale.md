# Sensitivity and multiscale studies

AgencityStudio Plan 10 adds reproducible sensitivity studies derived from one completed canonical `AnalysisRun`.

The scientific boundary is strict:

```text
immutable canonical AnalysisRun
        ↓
explicit sensitivity configuration
        ↓
public AgencityLab 1.1.3 API
        ↓
immutable sensitivity result artifact
```

A sensitivity study never edits the base `AnalysisRun`, its source, its `SystemRevision`, or its physical/contextual parameter snapshot.

## Three different time concepts

`dt`, `tau`, and `w` remain three distinct concepts:

- `dt` is the observed sampling interval of the selected coordinate;
- `tau` is the physical/contextual characteristic structural time;
- `w` is the CRM memory window.

Plan 10 never assigns `tau = dt` or `w = dt`.

## Public AgencityLab 1.1.3 contracts inspected

### Tau multiscale

Studio uses only:

```python
from agencitylab.api import compute_agencity_spectrum
```

Public contract used by Studio:

```python
compute_agencity_spectrum(
    u,
    xi,
    taus,
    *,
    A_ref,
    P_c,
    windows=None,
    return_full=False,
)
```

The API returns the requested/evaluated `tau` scales, effective `w` values, time-resolved `b` and `beta` spectra, and Lab-produced summaries such as `b_mean`, `b_rms`, `beta_mean`, `J_mean`, and `S_mean`.

The `tau` grid is supplied explicitly by the user. Studio supports explicit lists and deterministic linear/logarithmic grid generation. These grid generators sample parameter space only; they do not infer a physical timescale from signal statistics.

> A multiscale maximum is a numerical result of the sensitivity study. It does not automatically redefine the physical `tau` stored in the SystemRevision.

Studio does not call `np.argmax`, FFT peak detection, autocorrelation, or another estimator to promote one scale to a physical parameter.

AgencityLab also contains a frequency-spectrum helper for `b` and public descriptive multiscale helpers. Plan 10 does not reinterpret a frequency peak as `tau`, and it does not automatically use an `optimal_tau` helper to rewrite the scientific context.

### `w` semantics during a tau sweep

If the base canonical Run requested an explicit `w`, Studio passes that exact scalar as `windows=w`. The Lab scan therefore varies `tau` while keeping the explicit `w` fixed.

If the base canonical Run requested `w` as unspecified, Studio passes:

```python
windows=None
```

for the multiscale call. Studio does **not** materialize `w=tau_i` itself. AgencityLab 1.1.3 applies its documented effective-window behavior and returns the effective `w` array. Both the original request mode and Lab-returned effective values remain visible in provenance.

A sweep with `w` unspecified is therefore scientifically distinct from a sweep with one explicit fixed `w`.

## Window sensitivity

Studio uses only:

```python
from agencitylab.api import optimize_agencity_window
```

Public contract used by Studio:

```python
optimize_agencity_window(
    u,
    xi,
    *,
    tau,
    A_ref,
    P_c,
    candidates=...,
    n_candidates=...,
)
```

AgencityLab 1.1.3 evaluates the Chapter-13 `Phi2` angular-stability criterion and returns all evaluated candidate windows, `phi2`, a `phi1_mean_abs_contrast` descriptive output, eligibility, `best_index`, and `w_opt`.

Plan 10 presents this as a **diagnostic/experimental numerical window-selection study**. The UI labels `w_opt` as a Lab-reported numerical optimum under the `Phi2` criterion.

> Window analysis does not silently replace the explicitly documented `w` of a scientific context.

A numerically favorable candidate is not automatically the physical/contextual memory of the system. Studio never writes `w_opt` into the base `SystemRevision` or `AnalysisRun`.

During a window study, `tau`, `A_ref`, `P_c`, source bytes, mapping, and `SystemRevision` remain fixed.

### Exact discrete candidates

The Lab window implementation represents CRM windows on the discrete sample grid. Studio therefore validates every requested `w` against the already established canonical sampling contract before queueing:

- finite and strictly positive;
- uniform/strictly increasing coordinate;
- exact integer multiple of `dt` within numerical machine tolerance;
- sufficient signal length for the window.

Studio rejects incompatible candidates instead of silently rounding them. The grid shown during Review is the grid sent to Lab.

## What is not implemented as a new Studio algorithm

Plan 10 does not copy any AgencityLab scientific implementation. In particular Studio does not implement:

- a private multiscale algorithm;
- a custom CRM window optimizer;
- a `tau × w` two-dimensional optimizer;
- FFT or autocorrelation estimation of physical `tau`;
- automatic fitting/calibration of `tau`, `w`, `A_ref`, or `P_c`;
- a new robustness score or peak detector;
- automatic Plan-9 diagnostics at every scale.

Experimental Phi1/Phi3 window helpers exposed by Lab are not turned into alternate automatic optimizers in this Plan. Their experimental contracts remain a future explicit extension if needed.

## SensitivityStudy

`SensitivityStudy` is the immutable reproducibility boundary. It pins:

- exact base `AnalysisRun`;
- canonical result SHA-256;
- source SHA-256;
- exact `SystemRevision` and system fingerprint;
- mapping snapshot;
- fixed parameter snapshot (`A_ref`, `P_c`, base `tau`, base requested `w`);
- study type (`TAU_MULTISCALE` or `W_SENSITIVITY`);
- grid-generation method and exact values;
- grid unit;
- public Lab API identifier;
- AgencityLab, Studio, and Python versions;
- deterministic execution fingerprint;
- immutable sensitivity result SHA-256.

Changing a grid or rerunning produces another study. Completed, failed, and cancelled studies are immutable historical records.

## Grid generation

Supported methods are:

- explicit values;
- linear range;
- logarithmic range.

Generated values are persisted exactly before execution. The configurable `SENSITIVITY_MAX_POINTS` limit is an operational safety limit, not a scientific constant. Studio rejects an oversized request; it never silently truncates it.

Plan 10 uses the same coordinate/`tau` unit already established by the canonical Run. It performs no hidden unit conversion during a sensitivity study.

## Celery execution

Only the study UUID is sent through Redis. The worker:

1. locks the study/state;
2. verifies pinned canonical and source hashes;
3. reloads the immutable source vectors and exact mappings;
4. reads fixed parameter snapshots;
5. calls the selected public AgencityLab API;
6. serializes the complete output;
7. publishes the artifact atomically;
8. stores its SHA-256 and manifest;
9. marks the study `COMPLETED`.

Duplicate deliveries are guarded by row locks and lifecycle states. Deterministic scientific errors are not retried as network failures.

## Result artifact

Sensitivity results use private `ZIP_NPY_JSON`, schema version 1:

- NumPy arrays are stored as `.npy` with original dtype and precision;
- complex `b`/`beta` spectrum arrays remain complex;
- JSON stores scalar metadata and the manifest;
- no pickle is used;
- the final exact bytes receive a SHA-256.

The canonical result artifact is never modified.

## Visualization

Plan 10 reuses the self-hosted Apache ECharts 6.1.0 bundle. The scale axis is `tau` or `w`, never the signal coordinate.

Lab-returned real metrics are plotted directly. When a Lab-returned metric such as `b_mean` is complex, the chart may display its magnitude explicitly as a **display-only representation**. The exact table retains the complex real/imaginary information from the artifact.

There is no automatic peak detection, curve normalization, or parameter promotion in the browser. Exact tables remain the accessible numerical fallback.

For tau studies, the table also exposes the Lab-returned effective `w` per scale. For window studies, the result page shows `w_opt` together with its `Phi2` criterion and an explicit warning that it is not automatically a physical constant.

## Permissions and privacy

Sensitivity studies reuse Analysis/Workspace permissions:

- Owner: create, run, rerun, inspect;
- Editor: create, run, rerun, inspect;
- Analyst: create, configure, run, rerun, inspect;
- Viewer: inspect completed studies only;
- non-member: object endpoints resolve as 404.

Artifacts and visualization endpoints remain private and `no-store`; server filesystem paths are never exposed.

## Scientific interpretation

Flat, unexpected, or structureless sensitivity results are valid software/scientific outputs. They are not failures simply because no preferred scale is visually obvious.

Plan 10 demonstrates software equivalence with AgencityLab's public sensitivity contracts for identical inputs. It does **not** claim that a numerical scale maximum validates the physical theory or identifies the true parameter of a real system.
