# Development guide

AgencityStudio is an orchestration and presentation application around the pinned public AgencityLab runtime. Contributors must preserve the boundary between physical/contextual configuration, canonical computation, diagnostics, sensitivity studies, multivariate execution and experimental observable spatial fields.

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

Operational settings include PostgreSQL/Redis connection values, private `DATASET_STORAGE_ROOT`, Dataset/preparation/Analysis bounds, visualization limits, `SENSITIVITY_MAX_POINTS` and the `FIELD_MAX_*` source/display guards. Operational limits are never theory constants or diagnostic thresholds.

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

The source adapter may materialize finite NumPy vectors, but it cannot scientifically repair them. Unit conversion belongs in an explicit PreparedDataArtifact. An unspecified `w` is passed as `None`; Studio does not substitute `tau` before the public Lab call.

Canonical result serialization preserves real/complex NumPy dtypes and uses `allow_pickle=False`. A Run becomes `COMPLETED` only after immutable artifact publication.

## Plan 9 diagnostic development

Diagnostics are a separate immutable execution boundary downstream of a completed canonical AnalysisRun:

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

It must not call `compute_agencity` again merely to obtain diagnostics, import `agencitylab.core`, calculate its own coherence/curvature/winding/regime/real-agencity formulas, use `np.angle(beta)` as structural orientation, or invent universal diagnostic thresholds.

Changing diagnostic configuration creates a new `DiagnosticRun` and fingerprint. The diagnostic task remains explicitly registered because it intentionally lives outside the default `tasks.py` autodiscovery path.

## Plan 10 sensitivity development

Sensitivity is another immutable boundary derived from one completed canonical Run:

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

The bridge may adapt representation only. Do not reproduce a multiscale loop or window criterion when the public Lab API already owns it. If base `w` is unspecified, pass `windows=None`; do not materialize `w=tau_i` in Studio. If base `w` is explicit, keep it fixed through a tau sweep. Never promote a numerical maximum or `w_opt` into physical context automatically.

## Plan 12 observable spatial field development

Plan 12 is explicitly **EXPERIMENTAL** and has a separate public integration boundary:

```text
immutable NPZ DatasetVersion
  ↓ exact u/t/coordinate/map materialization
immutable AnalysisRun snapshot
  ↓ transaction.on_commit
analyses.tasks -> analyses.field_tasks
  ↓
labbridge.fields
  ↓ public agencitylab.fields.compute_agencity_field
  ↓
private AnalysisResultArtifact (ZIP_NPY_JSON, N-D shapes preserved)
```

`labbridge.fields` is the only field-science call boundary. Studio must not loop over spatial locations to reimplement the canonical equations. The public Lab field API owns the local temporal orchestration.

### Field-source rules

Plan 12 reuses `Dataset` / immutable `DatasetVersion`; it does not create a second Data Workspace. NPZ is the minimum N-D source format. Inspection reads ZIP/NPY structure safely before large allocations, records each array key/shape/dtype/hash, rejects object dtype/pickle requirements and path traversal, and enforces configurable operational size/element limits.

Do not flatten `(time,x,y,...)` into tabular rows merely to reuse scalar machinery. Do not silently transpose, reshape or guess the time axis. Representation adaptation is allowed only when explicit and provenance-preserving.

### Field parameter rules

The public 1.1.3 field contract supports scalar/spatial `A_ref` and `tau`, `w=None`/scalar/spatial, and scalar/spatial/space-time `P_c`. Spatial maps are explicit physical/contextual inputs from immutable source arrays. Store map identity, shape, dtype, unit, SHA-256 and provenance in the Run snapshot.

When `w` is unspecified, pass literal `None`. AgencityLab may report an effective convention in result metadata; Studio records it separately and does not generate `w=tau` itself. `P_c=0` remains legal where Lab accepts it.

### Scientific boundary

The field result is `beta_obs(x,t)` / `b_obs(x,t)` derived from observable `u(x,t)`. It is not autonomous `phi(x,t)`. Production field code must contain no spatial CRM, gradient, Laplacian, PDE solver, autonomous-field evolution, domain-wall/vortex physics, thermodynamics or gravity.

No analysis-time interpolation, resampling, smoothing, filtering, filling, normalization or spatial averaging is permitted. No local statistics may generate `A_ref(x)`, `tau(x)`, `w(x)` or `P_c(x,t)`.

### Field result and reader

Serialize only public returned fields. Preserve exact N-D shape, axis order, dtype and complex values. `beta_obs` and `b_obs` remain aliases of stored Lab `beta` and `b`. If the public field result does not expose `theta`, Studio does not reconstruct it from `arg(beta_obs)`.

Private field endpoints expose manifest, exact spatial slices, exact point values and exact local temporal traces. Display-only downsampling never changes the artifact or exact-value endpoints.

## Failure handling

Use safe categories to distinguish result-input, Lab validation/execution, storage and Studio internal failures. Deterministic scientific validation errors are not endlessly retried.

Duplicate deliveries must observe persisted run/study state and one-to-one artifact constraints so only one artifact becomes authoritative.

## Visualization development

Canonical and diagnostic workspaces use `frontend/scripts/scientific-workspace.js`; sensitivity uses `sensitivity-workspace.js`; Plan 12 fields use `field-workspace.js`. All use pinned Apache ECharts 6.1.0 bundled locally.

The browser is presentation-only. It may request private payloads, plot already-computed values, perform labeled display-only complex representations, preserve exact indices and provide zoom/table alternatives. It may not calculate canonical science, diagnostics, field physics, peak selection, window criteria or physical-parameter estimates.

Structural orientation uses stored Lab `theta` only where that field exists. Missing orientation data is not reconstructed.

## Permissions and privacy

Scientific views/services resolve objects through Workspace/Project membership. Analyst is a scientific author role; Viewer is read-only. Non-members receive scoped 404 responses.

Private artifacts never receive public media URLs. Numerical endpoints use private/no-store responses and never expose storage paths.

## Testing rule

Tests verify software contracts and direct Lab equivalence. They do not prove the theory.

For Plan 12 compare both:

```text
direct public compute_agencity_field
vs
Studio -> labbridge.fields -> compute_agencity_field
```

and:

```text
selected field spatial trajectory
vs
direct public compute_agencity on the same local temporal series
```

Do not calculate expected scientific results with a Studio formula. A useful field debugging order is: source bytes → NPZ array → shape → time axis → spatial-axis order → parameter maps → labbridge arguments → direct Lab field → Studio field → serialized artifact → reader/slice.

Unexpected field results are scientifically useful. Do not alter `beta`, `J`, `D`, `S`, `Theta`, `tau`, `w`, `A_ref` or `P_c` merely to obtain smoother maps or passing tests.

## Worker and readiness

Dataset inspection, Prepared Data generation, canonical Analysis, DiagnosticRun, SensitivityStudy and observable-field Analysis execution are real worker workloads. Web and worker must share the private storage root.

`/health/ready/` checks PostgreSQL, Redis and compatible AgencityLab availability. It must not run `compute_agencity_field` or another scientific suite.

See `docs/analyses.md`, `docs/visualization.md`, `docs/testing.md` and `docs/observable-spatial-fields.md` for detailed contracts.
