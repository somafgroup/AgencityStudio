# Development guide

AgencityStudio is an orchestration and presentation application around the pinned public AgencityLab runtime. Contributors must preserve the boundary between physical/contextual configuration, canonical computation, diagnostics, sensitivity studies, multivariate execution, experimental observable spatial fields and autonomous Research fields.

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

Operational settings include PostgreSQL/Redis connection values, private `DATASET_STORAGE_ROOT`, Dataset/preparation/Analysis bounds, visualization limits, `SENSITIVITY_MAX_POINTS`, the `FIELD_MAX_*` source/display guards and the `RESEARCH_FIELD_MAX_*` execution/storage guards. Operational limits are never theory constants or diagnostic thresholds.

AgencityLab remains explicitly pinned to 1.2.0 for Studio 0.13.0. Do not silently install another Lab version merely to make a Studio test pass.

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

`labbridge.fields` is the only observable field-science call boundary. Studio must not loop over spatial locations to reimplement the canonical equations. The public Lab field API owns the local temporal orchestration.

### Field-source rules

Plan 12 reuses `Dataset` / immutable `DatasetVersion`; it does not create a second Data Workspace. NPZ is the minimum N-D source format. Inspection reads ZIP/NPY structure safely before large allocations, records each array key/shape/dtype/hash, rejects object dtype/pickle requirements and path traversal, and enforces configurable operational size/element limits.

Do not flatten `(time,x,y,...)` into tabular rows merely to reuse scalar machinery. Do not silently transpose, reshape or guess the time axis. Representation adaptation is allowed only when explicit and provenance-preserving.

### Field parameter rules

The public AgencityLab 1.2.0 field contract supports scalar/spatial `A_ref` and `tau`, `w=None`/scalar/spatial, and scalar/spatial/space-time `P_c`. Spatial maps are explicit physical/contextual inputs from immutable source arrays. Store map identity, shape, dtype, unit, SHA-256 and provenance in the Run snapshot.

When `w` is unspecified, pass literal `None`. AgencityLab may report an effective convention in result metadata; Studio records it separately and does not generate `w=tau` itself. `P_c=0` remains legal where Lab accepts it.

### Scientific boundary

The field result is `beta_obs(x,t)` / `b_obs(x,t)` derived from observable `u(x,t)`. It is not autonomous `phi(x,t)`. Observable-field production code must contain no spatial CRM, gradient, Laplacian, PDE solver, autonomous-field evolution, domain-wall/vortex physics, thermodynamics or gravity.

No analysis-time interpolation, resampling, smoothing, filtering, filling, normalization or spatial averaging is permitted. No local statistics may generate `A_ref(x)`, `tau(x)`, `w(x)` or `P_c(x,t)`.

### Field result and reader

Serialize only public returned fields. Preserve exact N-D shape, axis order, dtype and complex values. `beta_obs` and `b_obs` remain aliases of stored Lab `beta` and `b`. If the public field result does not expose `theta`, Studio does not reconstruct it from `arg(beta_obs)`.

Private field endpoints expose manifest, exact spatial slices, exact point values and exact local temporal traces. Display-only downsampling never changes the artifact or exact-value endpoints.

## Plan 13 autonomous Research field development

Plan 13 is explicitly **RESEARCH** and must remain separate from Plan 12 observable fields:

```text
explicit initial condition
  ↓
private ResearchFieldInputArtifact
  ↓ immutable AnalysisRun(kind=RESEARCH_FIELD)
transaction.on_commit
  ↓
analyses.tasks -> analyses.research_tasks
  ↓
labbridge.research
  ↓ public AgencityLab 1.2.0 research APIs only
  ↓
private AnalysisResultArtifact
```

`beta_obs(x,t)` and autonomous `phi(x,t)` are not interchangeable. A bridge exists only because Lab publicly exposes `agencitylab.fields.beta_to_phi`; Studio may call it only through the explicit Research initial-condition workflow and must freeze the source Run/result SHA and selected time index.

### Research public API boundary

`labbridge.research` may construct only documented public Lab objects and call documented public functions. Current integrated dynamics are `simulate_klein_gordon`, `simulate_dissipative_klein_gordon` and `simulate_tdgl`. Public coherent initializers are `domain_wall_profile` and `vortex_field`; the latter requires a caller-supplied radial-profile array. Topology uses public `phase_winding` on a caller-selected ordered contour. Thermodynamic post-processing is limited to the audited public functions `total_dissipated_power`, `total_entropy_production` and `field_agencial_entropy`.

Do not import `agencitylab.core`. Do not introduce Studio implementations of a PDE, Laplacian, gradient, finite-difference stencil, integrator, phase-winding formula, entropy formula, dissipation formula, temperature estimate, gravity equation or defect detector.

AgencityLab 1.2.0 exposes Gravity primitives/residuals but explicitly no Einstein solver. Gravity therefore remains unavailable as an executable Research module. Effective-beta is a separate public Research layer and remains out of Plan 13 scope; quantum is speculative and out of scope.

### Initial condition and grid rules

Every queued Research Run freezes exact `phi_0`, optional `phi_dot_0`, shape, dtype, axes and source metadata in a private artifact before the worker runs. Supported sources are only those represented by real public Lab contracts: pinned NPZ arrays, explicit public observable→phi bridge, public domain-wall initializer and public vortex initializer with supplied profile.

`UniformRectilinearGrid` requires finite, strictly increasing, uniformly spaced axes. Studio validates through the Lab constructor and does not resample a non-uniform grid automatically. Axis order is significant. Boundary kind and value are explicit and immutable.

For second-order dynamics, an omitted velocity may be represented only by the documented explicit zero-velocity initialization convention and that convention must be preserved in provenance. TDGL remains first-order and no synthetic `phi_dot` is stored.

### Numerical and model parameters

`lambda`, `mu` and, where required, `gamma` are Research model parameters with explicit provenance. `dt_solver` and `n_steps` are labelled **NUMERICAL METHOD**. They must never be reused as canonical `tau` or `w`.

`RESEARCH_FIELD_MAX_ELEMENTS`, `RESEARCH_FIELD_MAX_STEPS` and `RESEARCH_FIELD_MAX_OUTPUT_BYTES` are operational resource limits. Reject an oversized request; never silently shorten a trajectory or downcast/downgrade the science.

### Results and visualization

Research result serialization preserves the public `DynamicalAgencityFieldSolution` arrays, exact N-D shapes and complex dtypes with `allow_pickle=False`. Visualization reads stored artifacts only. `Re(phi)`, `Im(phi)`, `|phi|` and `arg(phi)` are display representations. `arg(phi)` is not automatically topology, and JavaScript must not infer a wall/vortex or thermodynamic quantity.

A successful Research Run confirms execution of the implemented mathematical model. It does not constitute experimental validation of its physical interpretation.

## Failure handling

Use safe categories to distinguish result-input, Lab validation/execution, storage and Studio internal failures. Deterministic scientific validation errors are not endlessly retried.

Duplicate deliveries must observe persisted run/study state and one-to-one artifact constraints so only one artifact becomes authoritative.

## Visualization development

Canonical and diagnostic workspaces use `frontend/scripts/scientific-workspace.js`; sensitivity uses `sensitivity-workspace.js`; Plan 12 fields use `field-workspace.js`; Plan 13 Research fields use `research-field-workspace.js`. All use pinned Apache ECharts 6.1.0 bundled locally.

The browser is presentation-only. It may request private payloads, plot already-computed values, perform labeled display-only complex representations, preserve exact indices and provide zoom/table alternatives. It may not calculate canonical science, diagnostics, field physics, topology, thermodynamics, peak selection, window criteria or physical/model-parameter estimates.

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

For every integrated Plan 13 module compare the direct public AgencityLab call with `Studio -> labbridge.research -> same public call`. Test the exact initial condition, axis order, boundary mapping, numerical parameters, complex preservation and explicit beta/phi bridge boundary. Unsupported modules must not acquire executable endpoints.

Do not calculate expected scientific results with a Studio formula. A useful Research debugging order is: input artifact → shape/axes → initial condition → boundary → model parameters → numerical method → labbridge arguments → direct Lab result → Studio result → serialization → reader.

Unexpected field results are scientifically useful. Do not alter canonical quantities or Research equations/model parameters merely to obtain smoother maps, a prettier wall/vortex or passing tests.

## Worker and readiness

Dataset inspection, Prepared Data generation, canonical Analysis, DiagnosticRun, SensitivityStudy, observable-field Analysis and Research-field Analysis execution are real worker workloads. Web and worker must share the private storage root.

`/health/ready/` checks PostgreSQL, Redis and compatible AgencityLab availability. It must not run `compute_agencity_field`, an autonomous solver or another scientific suite.

See `docs/analyses.md`, `docs/visualization.md`, `docs/testing.md`, `docs/observable-spatial-fields.md` and `docs/research-fields.md` for detailed contracts.
