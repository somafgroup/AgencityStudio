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
- `DATASET_STORAGE_ROOT`: private raw/prepared Dataset artifact root
- `DATASET_MAX_UPLOAD_BYTES`: maximum uploaded source bytes accepted by this Studio instance
- `DATASET_MAX_PASTE_BYTES`: maximum pasted source bytes accepted by this Studio instance
- `DATA_PREPARATION_MAX_ROWS`: maximum rows loaded by the current in-memory preparation engine
- `DJANGO_EMAIL_BACKEND`, `DJANGO_EMAIL_FILE_PATH`, `DJANGO_DEFAULT_FROM_EMAIL`
- SMTP variables `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`, credentials and TLS/SSL flags

Development defaults to Django's file email backend under `.emails/` so reset/invitation links are inspectable without printing bearer tokens into application logs. Tests use the in-memory backend. Production defaults to SMTP and remains provider-independent.

Production additionally supports `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_SECURE_SSL_REDIRECT` and the `DJANGO_SECURE_HSTS_*` settings.

Dataset/preparation size settings are operational protections, not limits of the Theory of Agencity. Do not turn Dataset statistics or preparation defaults into implicit physical parameters.

## Python

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e . pytest pytest-django ruff
python manage.py migrate
pytest
ruff check accounts config common datasets labbridge projects systems workspaces tests
```

After model work, always verify migration consistency:

```bash
python manage.py makemigrations --check --dry-run
```

AgencityLab is installed through Studio's pinned runtime dependency. Do not install a different Lab version silently to make a Studio workflow pass; update the explicit compatibility contract in a dedicated change when a new Lab release is adopted.

## Accounts, workspaces and Projects

Local accounts use email as the login identifier. `User.objects.create_user()` creates the personal workspace transactionally. Organisation workspaces, memberships, invitation acceptance, role changes and removal use explicit workspace services; views and future APIs should reuse those invariants instead of duplicating them.

Projects are Workspace-owned containers. Project deletion remains conservative because Datasets and Systems sit below the Project boundary: a Project with either retained Datasets or Systems cannot be hard-deleted until those scientific resources have been handled explicitly.

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

`ObservableDefinition` describes scientific meaning and is intentionally separate from `DatasetColumn`. Plan 6 does not persist a Dataset-column-to-observable mapping; future Analysis configuration will make that association explicitly.

`A_ref`, `tau`, `w` and `P_c` are explicit physical/contextual fields with original value text, unit, origin and justification. `w=UNSPECIFIED` is a real provenance state and must not be stored as an invented numeric value. The future analysis layer may record AgencityLab's documented `w=tau` resolution when it actually executes Lab.

Unit checking reuses the shared Pint-backed helper in `common.units`. Known units receive dimensional checks; unknown labels are preserved and reported as not automatically validated. Do not silently convert the stored representation or treat unknown units as dimensionless.

`labbridge.scientific_context` may inspect the public AgencityLab 1.1.3 signature and mirror public scalar input validation. It must not call `compute_agencity()` or import `agencitylab.core`.

## Frontend

```bash
npm install
npm run build
```

Use the watch scripts from `package.json` while editing Tailwind or JavaScript. Generated `static/css/app.css` and `static/js/app.js` files are build artifacts and remain ignored.

Dataset/preparation preview and status refresh use server-rendered HTMX endpoints. Alpine may manage local form visibility/reordering affordances only. Business rules and permission checks must work without JavaScript.

System forms remain server-authoritative. Client-side help or progressive-disclosure controls may improve the guided experience, but scientific validation, permissions, revision creation and unit contracts must remain on the server.

## Worker

With Redis available at `REDIS_URL`:

```bash
celery -A config worker --loglevel=INFO
```

The deterministic infrastructure task can verify the actual broker/worker/result path:

```bash
python -c "from config import celery_app; result = celery_app.send_task('common.health_ping'); print(result.get(timeout=10))"
```

Dataset import inspection and prepared-data materialization are real worker workloads. Web and worker processes must share access to `DATASET_STORAGE_ROOT` for the current local filesystem backend; Docker Compose mounts the same private volume into both services.

System identity and revision creation remain synchronous database transactions. Do not introduce Celery for these fast metadata operations.

## Scientific implementation rule

Studio may import documented AgencityLab public APIs through `labbridge`. Raw Dataset import/inspection, generic Data Preparation and Plan 6 System documentation do not execute the Agencity pipeline.

Do not copy formulas, reach into AgencityLab private/core modules, infer `A_ref`, `tau`, `w` or `P_c`, or silently preprocess raw DatasetVersions. In Plan 5, crop, row exclusion, interpolation, resampling, smoothing, unit conversion, column selection and sorting happen only when the user adds a defined transformation to a recipe.

`dt` used by a resampling operation is a sampling interval. It is not `tau` and not CRM window `w`. A System revision documents `tau` and `w` independently from acquisition properties.

The architecture is deliberately:

```text
DatasetVersion / PreparedDataArtifact   SystemRevision
                \                         /
                 \   future Analysis    /
                  -----------------------
```

Plan 6 must not create `AnalysisRun`, execute `compute_agencity`, or persist `beta`, `b` or any other Agencity result.

See `docs/datasets.md` for immutable raw-data contracts, `docs/data-preparation.md` for preparation/provenance contracts and `docs/systems.md` for scientific-context versioning and parameter provenance.
