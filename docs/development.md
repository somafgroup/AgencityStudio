# Development guide

The repository is designed so contributors can work through Docker Compose or run the Django/frontend processes directly while PostgreSQL and Redis remain external services.

## Environment

Copy `.env.example` to `.env` for Docker Compose. The example is development-only; never reuse its secret or database password in production.

Important variables:

- `DJANGO_SETTINGS_MODULE`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `AGENCITYSTUDIO_SIGNUP_MODE`: `public`, `invitation_only` or `disabled`
- `WORKSPACE_INVITATION_TTL`: invitation lifetime in seconds
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
- `REDIS_URL`
- `DATASET_STORAGE_ROOT`: private raw/prepared/result artifact root shared by web and worker
- `DATASET_MAX_UPLOAD_BYTES`: maximum uploaded source bytes accepted by this Studio instance
- `DATASET_MAX_PASTE_BYTES`: maximum pasted source bytes accepted by this Studio instance
- `DATA_PREPARATION_MAX_ROWS`: maximum rows loaded by the current in-memory preparation engine
- `ANALYSIS_MAX_ROWS`: maximum rows materialized by the current canonical execution adapter
- `VISUALIZATION_MAX_POINTS`: maximum original result samples sent to one chart representation
- `VISUALIZATION_TABLE_PAGE_SIZE`: exact canonical table rows rendered per server page
- `DJANGO_EMAIL_BACKEND`, `DJANGO_EMAIL_FILE_PATH`, `DJANGO_DEFAULT_FROM_EMAIL`
- SMTP variables `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`, credentials and TLS/SSL flags

Development defaults to Django's file email backend under `.emails/` so reset/invitation links are inspectable without printing bearer tokens into application logs. Tests use the in-memory backend. Production defaults to SMTP and remains provider-independent.

Production additionally supports `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_SECURE_SSL_REDIRECT` and the `DJANGO_SECURE_HSTS_*` settings.

Dataset/preparation/analysis size settings and visualization point/page limits are operational protections, not limits of the Theory of Agencity. Do not turn Dataset statistics, preparation defaults or visualization density into implicit physical parameters or scientific thresholds.

## Python

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e . pytest pytest-django ruff
python manage.py migrate
pytest
ruff check accounts analyses config common datasets labbridge projects systems workspaces tests
```

After model work, always verify migration consistency:

```bash
python manage.py makemigrations --check --dry-run
```

AgencityLab is installed through Studio's pinned runtime dependency. Do not install a different Lab version silently to make a Studio workflow pass; update the explicit compatibility contract in a dedicated change when a new Lab release is adopted.

## Accounts, workspaces and Projects

Local accounts use email as the login identifier. `User.objects.create_user()` creates the personal workspace transactionally. Organisation workspaces, memberships, invitation acceptance, role changes and removal use explicit workspace services; views and future APIs should reuse those invariants instead of duplicating them.

Projects are Workspace-owned containers. Project deletion remains conservative because Datasets, Systems and Analyses sit below the Project boundary: a Project with retained scientific resources cannot be hard-deleted until those resources have been handled explicitly.

The development admin remains available at `/admin/` to instance staff. Workspace Owner is a separate application role and never grants Django Admin access.

## Dataset development

Dataset code lives under `datasets/`. Raw import keeps small explicit layers:

```text
views/forms
    ↓
services
    ↓
models + storage + importers
    ↓
Celery inspection task
```

Django views must not absorb importer/parser logic. Importers support delimited text and XLSX. Raw artifacts are immutable; new source bytes always mean a new DatasetVersion.

Use `DatasetColumn.position` together with `source_name` rather than assuming headers are unique. Do not normalize or rename source headers as provenance.

Reprocessing may alter parsing configuration and derived inspection metadata, but it must never alter the raw artifact. Increment the inspection generation before enqueueing so stale worker deliveries cannot overwrite a newer result.

A Dataset answers what data are available. It does not identify the physical system those measurements represent. Never attach System semantics automatically from a Dataset column or use observed `dt`, statistics, ranges or quality findings to populate `A_ref`, `tau`, `w` or `P_c`.

## Preparation development

The prepared-data path is separate from raw import:

```text
preparation_views/forms
        ↓
preparation_services
        ↓
controlled preparation registry/engine
        ↓
Celery preparation task
        ↓
immutable PreparedDataArtifact
```

A transformation belongs in Studio only when it is generic, explicit data preparation. Before adding a scientific operation, check whether AgencityLab already owns it through a documented public API. Never import `agencitylab.core` or copy a canonical equation into a preparation module.

Every preparation operation must have a stable operation identifier, JSON-safe explicit parameters, validation, deterministic execution contract and provenance representation. Browser input must never become Python code, shell commands, arbitrary filesystem paths or SQL.

A Draft can change. Once queued/executed, its source version and recipe record are frozen by policy; changes require a duplicate/new run. Result files are written once through private storage and get their own exact-byte SHA-256.

The current engine uses NumPy for deterministic tabular numeric work and Pint for compatible unit conversion. It intentionally does not add SciPy merely to expose a generic filter. If filtering is added later, define sampling assumptions, cutoff/order, phase behavior and anti-alias behavior first.

`DATA_PREPARATION_MAX_ROWS` bounds current worker memory use. Do not advertise arbitrary huge-file preparation until a streaming/out-of-core implementation has actually been built and tested.

When a new task depends on freshly committed Dataset/preparation metadata, enqueue it with `transaction.on_commit()`.

## System scientific-context development

System code lives under `systems/`. A `System` is a stable Project-owned identity; a `SystemRevision` is an immutable snapshot of its scientific context. Scientific edits therefore create a new revision and update `System.current_revision` transactionally instead of rewriting history.

Use `systems.services` for create/revise/duplicate/archive/restore/delete workflows. Revision numbering is allocated while holding a row lock on the owning System and is also protected by the database unique constraint. Do not mass-assign `project`, `created_by`, `revision_number` or `current_revision` from browser input.

`ObservableDefinition` describes scientific meaning and is intentionally separate from `DatasetColumn`. Analysis configuration makes that association explicitly by pinning a stable source column position and an exact ObservableDefinition.

`A_ref`, `tau`, `w` and `P_c` are explicit physical/contextual fields with original value text, unit, origin and justification. `w=UNSPECIFIED` is a real provenance state and must not be stored as an invented numeric value. Analysis passes that state to Lab as `w=None` and may record the effective public result `memory_window` after Lab actually executes.

Unit checking reuses the shared Pint-backed helper in `common.units`. Known units receive dimensional checks; unknown labels are preserved and reported as not automatically validated. Do not silently convert the stored representation or treat unknown units as dimensionless.

`labbridge.scientific_context` may inspect the public AgencityLab 1.1.3 signature and mirror public scalar input validation. It must not import `agencitylab.core`.

## Canonical Analysis development

Analysis code lives under `analyses/`. Keep the execution path explicit:

```text
views/forms
    ↓
analyses.services
    ↓ immutable AnalysisRun snapshot
transaction.on_commit()
    ↓
Celery task with Run UUID only
    ↓
source adapter + structural preflight
    ↓
labbridge.execute_canonical_analysis
    ↓ public agencitylab.compute_agencity
    ↓
private versioned result artifact
```

`Analysis` is a mutable named workspace. `AnalysisRun` is the immutable reproducibility boundary. Never resolve `Dataset.current_version` or `System.current_revision` inside a historical Run. Source, mapping, SystemRevision, parameters, versions and execution fingerprint must already be pinned.

The source adapter may convert stored tabular representations to finite NumPy vectors, but it must not sort, drop, fill, interpolate, resample, smooth, filter, standardize, normalize or convert units. If data require those operations, direct the user to explicit Data Preparation.

The execution unit policy is deliberately strict: source and System unit labels used by the numeric execution must match exactly. Pint may establish that different labels are dimensionally compatible, but Analysis must not silently scale values. Put unit conversion in a PreparedData recipe so the transformed bytes and provenance are explicit.

Preflight may explain public input conditions already known from AgencityLab 1.1.3, such as finite one-dimensional samples, increasing/uniform numeric coordinate and compatibility of an explicit `w` with observed `dt`. When `w` is unspecified, Studio must not substitute `tau` to imitate Lab. Pass `w=None` and let Lab be authoritative.

Only `labbridge.execution` calls `compute_agencity`. It must pass Studio-validated representation values and public metadata through unchanged, capture public Lab warnings and normalize public Lab exceptions. It must never recalculate, repair or reinterpret canonical quantities.

Canonical result serialization uses a schema-versioned ZIP with a JSON manifest and `.npy` arrays written with `allow_pickle=False`. Preserve dtypes and complex components exactly; do not downcast `float64`/`complex128`. The writer publishes atomically, and a Run becomes `COMPLETED` only after the one-to-one result artifact is stored.

A duplicate Celery delivery must stop at the Run status guard. Deterministic scientific validation failures are not retryable infrastructure events. Queued cancellation is supported; a synchronous running Lab call is not falsely marked cancelled.

## Canonical visualization development

Visualization remains downstream of a completed immutable Run:

```text
AnalysisResultArtifact
    ↓
AnalysisResultReader
    ↓
analyses.visualization
    ↓
visualization_views
    ↓
ScientificWorkspaceController
```

`AnalysisResultReader` is the only visualization layer that knows ZIP member paths. Extend it with read-only schema-aware operations rather than opening ZIP files in multiple views. Schema changes must keep readers for supported historical versions; never rewrite old result artifacts in place.

`analyses.visualization` may select exact ranges, select display indices, serialize values safely and expose presentation metadata. It must not call Lab or reproduce `J`, `Theta`, `U`, `beta`, `b`, CRM, or any other canonical computation. Real/imaginary/magnitude/phase of an already stored complex value are display transformations only.

Structural orientation uses stored `theta`. Never implement a fallback based on `np.angle(beta)`, a browser phase, or reconstructed M/O. A missing `theta` means the orientation chart is unavailable for that artifact.

Display decimation must preserve original result indices. It cannot feed Analysis execution, diagnostics, scientific exports or exact selected-sample values. The exact inspector must fetch `sample(index)` from the full-resolution result.

Visualization endpoints must reuse Run Workspace permission lookup, return 404 to a non-member, use private/no-store cache headers, and never serialize `storage_path`, absolute filesystem roots or backend implementation details.

The exact table stays in original sample order. Do not add sorting by D, beta, b, magnitude, or any other scientific value because that would break the coordinate/sample relation.

Do not add coherence, angular variance, curvature, winding, zero/event/transition detection, regime classification or real-agencity inference to visualization code. Those belong to a separate diagnostic layer.

## Frontend

```bash
npm install
npm run build
```

Use the watch scripts from `package.json` while editing Tailwind or JavaScript. `npm run watch:science` rebuilds the dedicated Results bundle. Generated `static/css/app.css`, `static/js/app.js` and `static/js/scientific-workspace.js` files are build artifacts and remain ignored.

Dataset/preparation/Analysis status refresh uses server-rendered HTMX endpoints. Alpine may manage local form visibility/reordering affordances only. Business rules and permission checks must work without JavaScript. No browser code calculates `J`, `beta`, `b` or any other canonical quantity.

Apache ECharts 6.1.0 is imported modularly by `frontend/scripts/scientific-workspace.js`. Keep it out of the global app bundle and do not add a CDN fallback. The controller must stay scoped to one Results workspace and must not become a global scientific-data store.

Chart clicks and sample controls carry original sample indices. A chart may use display-decimated points, but the inspector must request the exact sample endpoint. Avoid interpolated scientific tooltips between samples.

Chart theme changes use the existing `agencity:theme-changed` event and CSS variables. Preserve Light/Dark/System behavior and `prefers-reduced-motion`; playback never starts automatically.

System and Analysis forms remain server-authoritative. Client-side help or progressive-disclosure controls may improve the guided experience, but scientific validation, permissions, snapshots and unit contracts remain on the server.

## Worker

With Redis available at `REDIS_URL`:

```bash
celery -A config worker --loglevel=INFO
```

The deterministic infrastructure task can verify the actual broker/worker/result path:

```bash
python -c "from config import celery_app; result = celery_app.send_task('common.health_ping'); print(result.get(timeout=10))"
```

Dataset import inspection, prepared-data materialization and canonical Analysis execution are real worker workloads. Web and worker processes must share access to `DATASET_STORAGE_ROOT` for the current local filesystem backend; Docker Compose mounts the same private volume into both services.

Displaying a completed result is not a Celery workload. Do not turn each chart request into a task unless future profiling demonstrates a genuinely expensive, regenerable technical cache requirement.

System identity and revision creation remain synchronous database transactions. Do not introduce Celery for these fast metadata operations.

## Scientific implementation rule

Studio may import documented AgencityLab public APIs through `labbridge`. Plan 7 canonical execution calls the package-root `compute_agencity` and stores what Lab returns. Plan 8 only reads that stored result.

Do not copy formulas, reach into AgencityLab private/core modules, infer `A_ref`, `tau`, `w` or `P_c`, silently preprocess selected DatasetVersion/PreparedDataArtifact values, or silently derive missing result series. `dt` is a sampling interval, not `tau` and not CRM window `w`.

The architecture is deliberately:

```text
DatasetVersion / PreparedDataArtifact   SystemRevision
                \                         /
                 \      Analysis         /
                  ------ AnalysisRun -----
                           ↓
                  public AgencityLab
                           ↓
                  immutable result
                           ↓
                  read-only visualization
```

A successful canonical result must not be labelled coherent, stable, chaotic or “real agencity” without the separate future diagnostic layer.

See `docs/datasets.md` for immutable raw-data contracts, `docs/data-preparation.md` for preparation/provenance contracts, `docs/systems.md` for scientific-context versioning and parameter provenance, `docs/analyses.md` for the complete canonical execution contract, and `docs/visualization.md` for Plan 8 development constraints.
