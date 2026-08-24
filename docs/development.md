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
ruff check accounts config common datasets labbridge projects workspaces tests
```

After model work, always verify migration consistency:

```bash
python manage.py makemigrations --check --dry-run
```

AgencityLab is installed through Studio's pinned runtime dependency. Do not install a different Lab version silently to make a Studio workflow pass; update the explicit compatibility contract in a dedicated change when a new Lab release is adopted.

## Accounts, workspaces and Projects

Local accounts use email as the login identifier. `User.objects.create_user()` creates the personal workspace transactionally. Organisation workspaces, memberships, invitation acceptance, role changes and removal use explicit workspace services; views and future APIs should reuse those invariants instead of duplicating them.

Projects are Workspace-owned containers. Project deletion remains conservative because Datasets sit below the Project boundary: a Project with Datasets cannot be hard-deleted until the scientific sources have been handled explicitly.

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

## Frontend

```bash
npm install
npm run build
```

Use the watch scripts from `package.json` while editing Tailwind or JavaScript. Generated `static/css/app.css` and `static/js/app.js` files are build artifacts and remain ignored.

Dataset/preparation preview and status refresh use server-rendered HTMX endpoints. Alpine may manage local form visibility/reordering affordances only. Business rules and permission checks must work without JavaScript.

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

## Scientific implementation rule

Studio may import documented AgencityLab public APIs through `labbridge`. Raw Dataset import/inspection and generic Data Preparation do not execute the Agencity pipeline.

Do not copy formulas, reach into AgencityLab private/core modules, infer `A_ref`, `tau`, `w` or `P_c`, or silently preprocess raw DatasetVersions. In Plan 5, crop, row exclusion, interpolation, resampling, smoothing, unit conversion, column selection and sorting happen only when the user adds a defined transformation to a recipe.

`dt` used by a resampling operation is a sampling interval. It is not `tau` and not CRM window `w`.

See `docs/datasets.md` for immutable raw-data contracts and `docs/data-preparation.md` for preparation/provenance contracts.
