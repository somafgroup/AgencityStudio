# Development guide

AgencityStudio is an orchestration and presentation application around the pinned public AgencityLab runtime. Contributors must preserve the boundary between physical/contextual configuration, canonical computation and downstream diagnostics.

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
ruff check accounts analyses config common datasets labbridge projects systems workspaces tests
pytest
```

Run the worker separately when testing asynchronous behavior:

```bash
celery -A config worker --loglevel=INFO
```

Important operational settings include PostgreSQL/Redis connection values, private `DATASET_STORAGE_ROOT`, Dataset/preparation/Analysis size bounds and visualization point/page bounds. Operational memory/display limits are not theory constants or diagnostic thresholds.

AgencityLab remains explicitly pinned. Do not silently install another Lab version merely to make a Studio test pass.

## Data and System boundaries

Raw DatasetVersions are immutable. Data Preparation creates explicit immutable derived artifacts with recorded operations. Analysis execution never silently sorts, fills, interpolates, resamples, smooths, filters, normalizes or converts the selected source.

A `SystemRevision` is an immutable scientific-context snapshot. `A_ref`, `tau`, `w` and `P_c` remain physical/contextual values with provenance. Do not infer them from standard deviation, MAD, range, spectrum, autocorrelation or observed sampling interval.

`w=UNSPECIFIED` is distinct from explicitly setting `w=tau`.

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

The diagnostic task intentionally lives in `analyses/diagnostic_tasks.py`, separate from canonical `analyses/tasks.py`. Because Celery autodiscovery normally targets `tasks.py`, `config/celery.py` explicitly imports the diagnostic module:

```python
app.conf.imports = ("analyses.diagnostic_tasks",)
```

Keep the worker-registration regression test when reorganizing tasks. A direct Python task test is not enough if a real Celery worker cannot discover the task.

### Failure handling

Use safe categories to distinguish result-input, Lab validation/execution, storage and Studio internal failures. Deterministic scientific validation errors are not endlessly retried.

Duplicate deliveries must observe persisted run state and one-to-one artifact constraints so only one artifact becomes authoritative.

## Visualization development

Canonical and diagnostic workspaces reuse `frontend/scripts/scientific-workspace.js` and Apache ECharts 6.1.0.

The browser is presentation-only. It may:

- request private manifest/series/sample payloads;
- plot already-computed series;
- perform display-only complex representations;
- keep an exact selected sample index;
- decimate display points while preserving original indices.

It may not calculate diagnostics or feed decimated values back into science.

The canonical and diagnostic templates must load the dedicated scientific stylesheet and JavaScript bundle explicitly inside the supported template blocks. `base.html` does not provide an `extra_head` block; follow the established Results workspace loading pattern.

Structural orientation always uses stored `theta`; missing orientation data makes the view unavailable rather than reconstructed.

## Permissions and privacy

Scientific views/services must resolve the object through Workspace/Project membership. Analyst is a scientific author role and can run diagnostics. Viewer is read-only. Non-members receive scoped 404 responses.

Private artifacts never receive public media URLs. Numerical endpoints use private/no-store responses and never expose storage paths.

## Testing rule

Tests verify software contracts and direct Lab equivalence. They do not prove the theory.

For diagnostics compare:

```text
direct public analyze_agencity
vs
Studio -> labbridge.diagnostics -> analyze_agencity
```

Do not calculate the expected result with a Studio formula. Preserve negative, empty, warning and `undetermined` outcomes exactly.

A useful scientific debugging order remains: find the first stage where software behavior diverges from the accepted contract. Do not alter `beta`, `J`, `D`, `S`, `Theta`, `tau`, `w`, `A_ref` or `P_c` merely to obtain prettier classifications.

## Worker and readiness

Dataset inspection, Prepared Data generation, canonical Analysis and DiagnosticRun execution are real worker workloads. Web and worker must share the private storage root.

`/health/ready/` checks PostgreSQL, Redis and compatible AgencityLab availability. It must not run a scientific analysis or diagnostic suite.

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
                    ┌───────┴────────┐
                    ↓                ↓
          canonical visualization   DiagnosticRun
                                     ↓
                              public analyze_agencity
                                     ↓
                           immutable diagnostic artifact
                                     ↓
                              diagnostic workspace
```

See `docs/analyses.md`, `docs/visualization.md` and `docs/diagnostics.md` for the detailed contracts. Multiscale `tau`/`w` sensitivity remains a later concern and must not be inferred from Plan 9.