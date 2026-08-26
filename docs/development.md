# Development guide

AgencityStudio is an orchestration and presentation application around the pinned public AgencityLab runtime. Contributors must preserve the boundary between physical/contextual configuration, canonical computation, diagnostics and sensitivity studies.

## Environment and validation

Use PostgreSQL and Redis for development paths that exercise persistence or workers. The normal local verification loop is:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e . pytest pytest-django ruff
npm install
npm run build
python manage.py migrate
python manage.py makemigrations --check --dry-run
ruff check accounts analyses config common datasets labbridge projects sensitivity systems workspaces tests
pytest
```

Run the worker separately when testing asynchronous behavior:

```bash
celery -A config worker --loglevel=INFO
```

Important operational settings include PostgreSQL/Redis connection values, private `DATASET_STORAGE_ROOT`, Dataset/preparation/Analysis size bounds, visualization point/page bounds and `SENSITIVITY_MAX_POINTS`. Operational memory/display/grid limits are not theory constants or diagnostic thresholds.

AgencityLab remains explicitly pinned. Do not silently install another Lab version merely to make a Studio test pass.

## Data and System boundaries

Raw DatasetVersions are immutable. Data Preparation creates explicit immutable derived artifacts with recorded operations. Analysis execution never silently sorts, fills, interpolates, resamples, smooths, filters, normalizes or converts the selected source.

A `SystemRevision` is an immutable scientific-context snapshot. `A_ref`, `tau`, `w` and `P_c` remain physical/contextual values with provenance. Do not infer them from standard deviation, MAD, range, spectrum, autocorrelation or observed sampling interval.

`w=UNSPECIFIED` is distinct from explicitly setting `w=tau`. `dt`, `tau` and `w` remain distinct.

## Canonical Analysis development

The canonical path is:

```text
views/forms
  ↓
analyses.services
  ↓ immutable AnalysisRun
transaction.on_commit
  ↓
analyses.tasks
  ↓
source adapter + structural validation
  ↓
labbridge.execution
  ↓ public agencitylab.compute_agencity
  ↓
private AnalysisResultArtifact
```

Only `labbridge.execution` calls the public canonical API. Do not duplicate `J`, `Theta`, `U`, `beta`, `b`, CRM or any other canonical equation in Studio.

The source adapter may materialize finite NumPy vectors, but it cannot scientifically repair them. Unit conversion belongs in an explicit PreparedDataArtifact.

An unspecified `w` is passed as `None`; Studio does not substitute `tau` before the public Lab call.

Canonical result serialization preserves real/complex NumPy dtypes and uses `allow_pickle=False`. A Run becomes `COMPLETED` only after immutable artifact publication.

## Plan 9 diagnostic development

Diagnostics are a second immutable execution boundary **downstream** of a completed canonical AnalysisRun:

```text
completed AnalysisRun + canonical result SHA
  ↓
DiagnosticRun
  ↓ transaction.on_commit
analyses.diagnostic_tasks
  ↓
labbridge.diagnostics
  ↓ public AgencityResult container
  ↓ public agencitylab.analyze_agencity
  ↓
private DiagnosticResultArtifact
```

The diagnostic bridge reads the exact stored canonical arrays. It reconstructs only the documented public `AgencityResult` container required by Lab and supplies stored canonical `theta` explicitly.

It must not:

- call `compute_agencity` again merely to obtain diagnostics;
- import `agencitylab.core` or another private Lab module;
- calculate its own coherence, angular variance, curvature, winding, zero/event, regime or real-agencity formulas;
- use `np.angle(beta)` as structural orientation;
- invent universal diagnostic thresholds.

If a required stored canonical series is missing, return an input/unavailable error rather than reconstructing science privately.

### Diagnostic configuration

`analyses.diagnostic_validation` validates structure only. Optional thresholds remain `None` unless explicitly supplied. User values are persisted and transmitted unchanged.

Contextual regime classification is disabled unless its criteria are explicitly supplied. Real-agencity assessment may remain `undetermined` when required thresholds are absent. This is correct behavior, not a reason to choose friendlier defaults.

Changing configuration creates a new `DiagnosticRun` and fingerprint.

### Diagnostic Celery registration

The diagnostic task intentionally lives in `analyses/diagnostic_tasks.py`, separate from canonical `analyses/tasks.py`. Because Celery autodiscovery normally targets `tasks.py`, `config/celery.py` explicitly imports the diagnostic module.

Keep the worker-registration regression test when reorganizing tasks. A direct Python task test is not enough if a real Celery worker cannot discover the task.

## Plan 10 sensitivity development

Sensitivity is a third immutable scientific-software boundary derived from one completed canonical Run:

```text
completed AnalysisRun
  ↓ exact source/hash/fixed context
SensitivityStudy
  ↓ transaction.on_commit
sensitivity.tasks
  ↓
labbridge.sensitivity
  ├─ public agencitylab.api.compute_agencity_spectrum
  └─ public agencitylab.api.optimize_agencity_window
  ↓
private SensitivityResultArtifact
```

The bridge may adapt representation only. Do not reproduce a multiscale loop or window criterion when the public Lab API already owns it. Do not import private Lab code.

### Tau multiscale

The grid is explicit user configuration. `EXPLICIT`, `LINEAR` and `LOG` generation only sample the requested parameter space; they are not estimators.

If base `w` is unspecified, pass `windows=None`. Do not write a Studio loop that replaces each point with `w=tau_i`. Record Lab-returned effective `w` values separately.

If base `w` is explicit, pass that scalar unchanged so it remains fixed across the tau sweep.

Never add `np.argmax`, an FFT peak, autocorrelation or another rule that changes the System or Analysis because one scale is numerically large.

### Window sensitivity

Use the public `optimize_agencity_window` API with the exact candidate list reviewed by the user. Because Lab windows are discrete in sample counts, prevalidate each candidate with the existing canonical `w/dt` contract. Reject incompatible values; do not silently round them.

Keep base `tau`, `A_ref`, `P_c`, source, mapping and SystemRevision fixed. The returned `w_opt` is a criterion-specific numerical output under Phi2, not a new physical/contextual memory value.

### Sensitivity storage and lifecycle

`SensitivityStudy` is immutable once finished. PostgreSQL stores identity/configuration/provenance; large Lab arrays remain in private `ZIP_NPY_JSON` artifacts. NumPy dtypes, including complex `b` and `beta` matrices, must not be downcast. Pickle is forbidden.

The Celery payload contains only the study UUID. The worker verifies canonical/source hashes before calling Lab and publishes the artifact atomically. Standard `sensitivity/tasks.py` is discovered through the installed Django app.

The configurable `SENSITIVITY_MAX_POINTS` limit is operational. Never silently truncate a larger scientific request.

## Failure handling

Use safe categories to distinguish result-input, Lab validation/execution, storage and Studio internal failures. Deterministic scientific validation errors are not endlessly retried.

Duplicate deliveries must observe persisted run/study state and one-to-one artifact constraints so only one artifact becomes authoritative.

## Visualization development

Canonical and diagnostic workspaces reuse `frontend/scripts/scientific-workspace.js`; sensitivity uses the scoped `frontend/scripts/sensitivity-workspace.js`. Both use the pinned Apache ECharts 6.1.0 package and are bundled locally.

The browser is presentation-only. It may:

- request private manifest/series/scale payloads;
- plot already-computed values;
- perform explicitly labeled display-only complex representations;
- preserve exact sample or scale indices;
- provide zoom and exact table alternatives.

It may not calculate canonical science, diagnostics, peak selection, window criteria or physical-parameter estimates.

Structural orientation always uses stored `theta`; missing orientation data makes the view unavailable rather than reconstructed.

Complex multiscale metrics may use magnitude in a chart only when explicitly labeled as a display representation. The exact table/artifact remains authoritative.

## Permissions and privacy

Scientific views/services must resolve the object through Workspace/Project membership. Analyst is a scientific author role and can run diagnostics and sensitivity studies. Viewer is read-only. Non-members receive scoped 404 responses.

Private artifacts never receive public media URLs. Numerical endpoints use private/no-store responses and never expose storage paths.

## Testing rule

Tests verify software contracts and direct Lab equivalence. They do not prove the theory.

For diagnostics compare:

```text
direct public analyze_agencity
vs
Studio -> labbridge.diagnostics -> analyze_agencity
```

For sensitivity compare the same public API both ways:

```text
direct compute_agencity_spectrum
vs
Studio -> labbridge.sensitivity -> compute_agencity_spectrum
```

and, for windows:

```text
direct optimize_agencity_window
vs
Studio -> labbridge.sensitivity -> optimize_agencity_window
```

Do not calculate expected scientific results with a Studio formula. Regression tests must also prove that unspecified `w` stays unspecified at the Studio/Lab boundary, explicit `w` stays fixed in a tau sweep, tau stays fixed in a window study, and no study mutates its base Run/SystemRevision.

A useful scientific debugging order remains: source → exact vectors → fixed snapshot → exact grid → labbridge arguments → direct Lab output → Studio Lab output → artifact serialization. Do not alter `beta`, `J`, `D`, `S`, `Theta`, `tau`, `w`, `A_ref` or `P_c` merely to obtain prettier results.

## Worker and readiness

Dataset inspection, Prepared Data generation, canonical Analysis, DiagnosticRun and SensitivityStudy execution are real worker workloads. Web and worker must share the private storage root.

`/health/ready/` checks PostgreSQL, Redis and compatible AgencityLab availability. It must not run a scientific analysis, diagnostic or sensitivity suite.

## Current scientific architecture

```text
DatasetVersion / PreparedDataArtifact     SystemRevision
                 \                         /
                  \      Analysis         /
                   ------ AnalysisRun -----
                            ↓
                  public compute_agencity
                            ↓
               immutable canonical artifact
             ┌──────────────┼─────────────────┐
             ↓              ↓                 ↓
   canonical visualization DiagnosticRun  SensitivityStudy
                            ↓                 ↓
                   public analyze_agencity   public multiscale/window APIs
                            ↓                 ↓
                 immutable diagnostic     immutable sensitivity
                       artifact               artifact
```

See `docs/analyses.md`, `docs/visualization.md`, `docs/diagnostics.md` and `docs/sensitivity-and-multiscale.md` for detailed contracts.
