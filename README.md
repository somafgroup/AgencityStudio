# AgencityStudio

AgencityStudio is the Web interface and orchestration layer for AgencityLab. It provides a browser-based scientific workspace while keeping all Agencity mathematics inside the AgencityLab public API.

## Current foundation

- Django 5.2 application served through ASGI/Uvicorn.
- PostgreSQL persistence.
- Redis-backed Celery worker execution.
- AgencityLab 1.1.3 pinned as the scientific runtime dependency.
- Server-rendered templates with Tailwind CSS, HTMX and Alpine.js.
- Local email/password authentication with Django sessions.
- Email-identified custom user accounts, profile and persisted preferences.
- Personal and organisation workspaces with explicit memberships.
- Workspace roles: Owner, Editor, Analyst and Viewer.
- Secure expiring workspace invitations whose raw tokens are not stored.
- Workspace-owned Projects with UUID identity, stable slugs, archive/restore, duplication and activity.
- Project-owned Datasets with immutable UUID DatasetVersions, exact-source SHA-256 fingerprints and private storage.
- CSV, TSV, structured TXT, XLSX and pasted tabular import with asynchronous inspection.
- Immutable NPZ DatasetVersions for exact N-dimensional observable-field sources, with pre-allocation header/size checks, object/pickle rejection, per-array shape/dtype/hash inventory and no silent flattening.
- Server-side Dataset preview, column roles/units, quality findings and version history.
- Explicit Data Preparation recipes pinned to an exact DatasetVersion.
- Immutable prepared artifacts with separate SHA-256, software provenance and prepared-data inspection.
- Explicit crop, row exclusion, missing-value treatment, linear interpolation, resampling, moving-average smoothing, compatible unit conversion, column selection and time sorting.
- Project-owned Systems with stable UUID identities and immutable scientific revisions.
- Explicit observable definitions, units, `A_ref`, `tau`, `w`, `P_c`, parameter origins, justifications and scientific references.
- Project-owned canonical Analyses with immutable numbered AnalysisRuns.
- Exact DatasetVersion or PreparedDataArtifact source pinning, exact SystemRevision pinning and explicit coordinate/observable mapping.
- Real Celery execution through the public `agencitylab.compute_agencity` API only.
- Private immutable canonical result artifacts preserving real and complex NumPy dtypes, with schema version and SHA-256.
- Per-Run source, parameter, software-version, execution-fingerprint and result-hash provenance.
- Read-only canonical Results workspace backed only by the immutable Run result artifact.
- Apache ECharts scientific visualization with linked coordinate views and complex planes for stored `U`, `beta` and `b`.
- Exact selected-sample inspector, server-paginated canonical table and display-only large-series decimation with original-index preservation.
- Immutable DiagnosticRuns derived from an exact completed AnalysisRun and pinned canonical result SHA-256.
- Public AgencityLab `analyze_agencity` execution through a dedicated diagnostic labbridge, with no copied diagnostic equations or private Lab imports.
- Private immutable diagnostic result artifacts, deterministic diagnostic fingerprints, threshold/configuration provenance and Lab warning preservation.
- Diagnostic workspace for coherence/orientation, geometry/topology, events/transitions, regimes and real-agencity evidence when supplied by AgencityLab 1.1.3.
- Exact sample synchronization between canonical and diagnostic workspaces with display-only diagnostic decimation.
- Immutable SensitivityStudies derived from completed canonical Runs, with exact scale grids, fixed-context snapshots and private result artifacts.
- Public AgencityLab `compute_agencity_spectrum` tau multiscale execution and `optimize_agencity_window` Phi2 window sensitivity only; no Studio scale optimizer.
- Explicit `dt` / `tau` / `w` separation, preservation of unspecified `w`, and no automatic promotion of a spectrum maximum or numerical `w_opt` into physical context.
- Exact sensitivity tables plus locally bundled Apache ECharts scale views; complex multiscale arrays retain full NumPy precision in storage.
- Multivariate Analyses using the public AgencityLab multivariate API, ordered component mappings and Lab-returned aggregate outputs only.
- **EXPERIMENTAL Observable Spatial Agencity Field Analyses** using only `agencitylab.fields.compute_agencity_field`, with explicit N-D shape/time-axis/spatial-axis contracts, scalar or spatial `A_ref`/`tau`/`w`, scalar/spatial/space-time `P_c`, immutable map provenance and lossless field artifacts.
- Observable-field ECharts workspaces for 1D time-space heatmaps, exact selected-time spatial maps/slices, exact point inspection and local temporal traces.
- Light, dark and system themes, including live chart re-theming.
- Chromium Playwright coverage for shell, account, workspace, invitation, Project, Dataset, preparation, System, Analysis, Results visualization, Diagnostics, Sensitivity and permission workflows.
- Docker Compose development/runtime stack.
- Liveness at `/health/` and dependency readiness at `/health/ready/`.

## Scientific boundary

Studio must never reproduce canonical equations or reach into private AgencityLab internals. Scientific computation enters through `labbridge`, which imports the documented AgencityLab package surface. The pinned runtime contract is currently AgencityLab `1.1.3`.

Identity, workspace and Project permissions are application concerns. Dataset inspection describes source data and data quality; it does not infer `A_ref`, `tau`, `w` or `P_c`, and it performs no Agencity calculation. Raw DatasetVersions are never silently sorted, filtered, interpolated, resampled, normalized or otherwise preprocessed.

Plan 5 adds a separate explicit preparation layer. A user may request defined transformations, which produce a new immutable prepared artifact while preserving the original DatasetVersion. Sampling interval `dt` used for resampling remains distinct from physical `tau` and CRM window `w`.

Plan 6 adds a separate scientific-context layer. A SystemRevision documents observables and physical/contextual `A_ref`, `tau`, `w` and `P_c` with units, origins and justifications. Studio does not derive these values from signal statistics, acquisition `dt`, a spectrum, autocorrelation or any other signal-derived heuristic. `w` left unspecified remains distinct from explicitly setting `w = tau`. No Agencity computation occurs in the Systems workspace.

Plan 7 adds canonical scalar execution without creating a second scientific implementation. An AnalysisRun pins the exact source artifact and SHA-256, stable column mapping, immutable SystemRevision and observable, physical/contextual parameter snapshot, AgencityLab/Studio/Python versions and execution fingerprint before the worker calls `agencitylab.compute_agencity`. Analysis execution never sorts, resamples, interpolates, filters, fills, normalizes or converts units. If preparation is required, it must already exist as an explicit PreparedDataArtifact. An unspecified `w` is passed to Lab as `None`; Studio never substitutes `w = tau` before the public API call. A successful Run means the canonical software computation and immutable result storage completed, not that coherent or “real” agencity was detected.

Plan 8 adds a read-only scientific visualization layer over that immutable Plan 7 result. Results pages do **not** call AgencityLab again. They read stored canonical arrays through a schema-aware ResultReader, expose private Workspace-scoped visualization endpoints, and render the stored values with a locally bundled Apache ECharts controller. `theta` is read from the stored AgencityLab result and is never reconstructed from `beta`. Real/imaginary/magnitude/phase representations of complex `U`, `beta` and `b` are display-only and are not persisted as new scientific results. Display decimation never changes the result artifact and exact selected-sample inspection always uses full-resolution stored values. Plan 8 itself performs no coherence, curvature, winding, transition, regime or real-agencity diagnostic.

Plan 9 adds a **separate diagnostic layer** downstream of the immutable canonical result. Studio reconstructs only the public `AgencityResult` container from the stored canonical arrays, explicitly supplies the stored canonical `theta`, and delegates diagnostic computation to the public `agencitylab.analyze_agencity` API. It does not rerun `compute_agencity`, copy diagnostic formulas, or substitute `arg(beta)` for structural orientation. A non-zero `beta` and a high `D` are not treated as proof of real agencity. Diagnostic thresholds are Lab-defined or explicit user configuration with provenance; Studio does not invent universal constants. Negative, empty, unknown and `undetermined` diagnostic outcomes are preserved as valid scientific-software results.

Plan 10 adds a third, explicitly derived **sensitivity layer**. Tau multiscale studies send an exact user-chosen `tau` grid to public `agencitylab.api.compute_agencity_spectrum`. Window studies send exact `w` candidates to public `agencitylab.api.optimize_agencity_window`, whose `Phi2` optimum remains a criterion-dependent numerical result. `dt`, `tau` and `w` remain distinct. With unspecified base `w`, Studio passes `windows=None` and records the effective Lab-returned windows rather than materializing `w=tau` itself. With explicit base `w`, that value remains fixed through a tau sweep. A window sweep keeps `tau`, `A_ref`, `P_c`, source, mapping and SystemRevision fixed. No maximum or optimum mutates the base Run or scientific context.

Plan 11 adds the public multivariate Analysis path while preserving component order, component-specific physical snapshots and Lab-returned aggregate quantities. Studio neither invents nor recomputes a multivariate aggregation.

Plan 12 adds the first spatial extension with scientific status **EXPERIMENTAL**. Studio sends one exact N-dimensional observable source to public `agencitylab.fields.compute_agencity_field`. CRM remains temporal and independent at each spatial location. `beta_obs(x,t)` and `b_obs(x,t)` are observable fields derived from `u(x,t)` and are **not** the autonomous dynamical field `phi(x,t)`. Plan 12 introduces no spatial CRM, spatial derivative, PDE, autonomous-field evolution, domain-wall/vortex physics, thermodynamics or gravity. Spatial physical parameter maps must be explicitly supplied and justified; Studio never derives them from local signal statistics. An unspecified field `w` is submitted as literal `None`, with any effective resolution delegated to AgencityLab.

Frequency filtering remains deliberately deferred until a precise sampling/cutoff/order/phase/anti-alias contract is implemented. Studio does not introduce hidden filter defaults merely to expose another preprocessing option.

## Quick start with Docker Compose

```bash
cp .env.example .env
docker compose build
docker compose up -d postgres redis
docker compose run --rm web python manage.py migrate --noinput
docker compose up -d web worker
```

Open `http://localhost:8000/`, create a local account and AgencityStudio will create its private personal workspace. Projects organise the scientific work. The Data Workspace can import immutable raw tabular sources and immutable NPZ field sources; the Prepare tab can materialize explicit tabular derived views; the Systems tab documents versioned scientific context independently from data artifacts; and the Analyses tab can queue scalar, multivariate or observable-field AgencityLab execution. A completed observable field Run opens a read-only field workspace with exact provenance and exact space-time inspection.

The readiness endpoint should return HTTP 200 once PostgreSQL, Redis and the compatible AgencityLab runtime are available:

```bash
curl http://localhost:8000/health/ready/
```

Development email defaults to files under `.emails/`; this keeps password-reset and invitation bearer links out of console/application logs. Production defaults to provider-independent SMTP configuration.

Public signup behavior is controlled by:

```text
AGENCITYSTUDIO_SIGNUP_MODE=public
AGENCITYSTUDIO_SIGNUP_MODE=invitation_only
AGENCITYSTUDIO_SIGNUP_MODE=disabled
```

Dataset/preparation/analysis storage and visualization payloads are protected by configurable instance limits:

```text
DATASET_MAX_UPLOAD_BYTES=<bytes>
DATASET_MAX_PASTE_BYTES=<bytes>
DATASET_STORAGE_ROOT=<private path>
DATA_PREPARATION_MAX_ROWS=<rows>
ANALYSIS_MAX_ROWS=<rows>
VISUALIZATION_MAX_POINTS=<display points>
VISUALIZATION_TABLE_PAGE_SIZE=<rows per page>
SENSITIVITY_MAX_POINTS=<scale candidates per study>
FIELD_MAX_UPLOAD_BYTES=<bytes>
FIELD_MAX_ARRAYS=<arrays per NPZ>
FIELD_MAX_ELEMENTS=<total declared elements>
FIELD_MAX_UNCOMPRESSED_BYTES=<bytes>
FIELD_MAX_DISPLAY_POINTS=<display-only points>
```

These are operational memory, storage and browser-safety limits, never scientific thresholds. Field limits reject an oversized source clearly; they never truncate scientific arrays or silently calculate only part of a field.

See `docs/accounts-and-workspaces.md` for identity/workspace semantics, `docs/datasets.md` for raw Dataset contracts, `docs/data-preparation.md` for prepared-data lineage and transformations, `docs/systems.md` for scientific System revisions and physical/contextual parameter provenance, `docs/analyses.md` for execution and reproducibility, `docs/visualization.md` for presentation contracts, `docs/diagnostics.md` for diagnostics, `docs/sensitivity-and-multiscale.md` for Plan 10 semantics, and `docs/observable-spatial-fields.md` for the exact Plan 12 field contract.

To verify the asynchronous worker path end to end through Studio's configured Celery application:

```bash
docker compose exec web python -c "from config import celery_app; result = celery_app.send_task('common.health_ping'); print(result.get(timeout=10))"
```

Expected output: `pong`.

## Local development without Docker for the web process

Install the Python and frontend dependencies, provide PostgreSQL/Redis through the environment, then build the assets:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e . pytest pytest-django ruff
npm install
npm run build
python manage.py migrate
uvicorn config.asgi:application --reload
```

Run a worker separately:

```bash
celery -A config worker --loglevel=INFO
```

## Validation

The CI pipeline checks Python quality, Django configuration, production settings, migration consistency, PostgreSQL migrations, backend identity/workspace/Project/Dataset/preparation/System/Analysis/visualization/diagnostic/sensitivity/multivariate/field permission and provenance tests, direct AgencityLab-versus-labbridge equivalence, local field-versus-direct-scalar equivalence, exact result-reader and complex-value preservation, frontend build, critical Playwright flows with real workers, Docker image construction, Compose readiness and an actual Celery task round trip.

Additional documentation lives under `docs/`, especially `docs/architecture.md`, `docs/accounts-and-workspaces.md`, `docs/projects.md`, `docs/datasets.md`, `docs/data-preparation.md`, `docs/systems.md`, `docs/analyses.md`, `docs/visualization.md`, `docs/diagnostics.md`, `docs/sensitivity-and-multiscale.md`, `docs/observable-spatial-fields.md`, `docs/development.md`, `docs/testing.md` and `docs/ui.md`.
