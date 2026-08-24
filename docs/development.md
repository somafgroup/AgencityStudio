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
- `DATASET_STORAGE_ROOT`: private raw Dataset artifact root
- `DATASET_MAX_UPLOAD_BYTES`: maximum uploaded source bytes accepted by this Studio instance
- `DATASET_MAX_PASTE_BYTES`: maximum pasted source bytes accepted by this Studio instance
- `DJANGO_EMAIL_BACKEND`, `DJANGO_EMAIL_FILE_PATH`, `DJANGO_DEFAULT_FROM_EMAIL`
- SMTP variables `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`, credentials and TLS/SSL flags

Development defaults to Django's file email backend under `.emails/` so reset/invitation links are inspectable without printing bearer tokens into application logs. Tests use the in-memory backend. Production defaults to SMTP and remains provider-independent.

Production additionally supports `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_SECURE_SSL_REDIRECT` and the `DJANGO_SECURE_HSTS_*` settings.

Dataset size settings are operational protections, not limits of the Theory of Agencity. Do not turn Dataset statistics into implicit physical parameters.

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

Local accounts use email as the login identifier. `User.objects.create_user()` creates the personal workspace transactionally. Organisation workspaces, memberships, invitation acceptance, role changes and removal use the explicit services under `workspaces.services`; views and future APIs should reuse those invariants instead of duplicating them.

Projects are Workspace-owned containers. Project deletion must remain conservative because Datasets now sit below the Project boundary: a Project with Datasets cannot be hard-deleted until the scientific sources have been handled explicitly.

The development admin remains available at `/admin/` to instance staff. Workspace Owner is a separate application role and never grants Django Admin access.

See `docs/accounts-and-workspaces.md` and `docs/projects.md` for the related contracts.

## Dataset development

Dataset code lives under `datasets/`. Keep the layers small and explicit:

```text
views/forms
    ↓
services
    ↓
models + storage + importers
    ↓
Celery inspection task
```

Django views must not absorb importer/parser logic. Importers currently support delimited text and XLSX. Raw artifacts are immutable; new source bytes always mean a new DatasetVersion.

Use `DatasetColumn.position` together with `source_name` rather than assuming headers are unique. Do not normalize or rename source headers as provenance.

Reprocessing may alter parsing configuration and derived inspection metadata, but it must never alter the raw artifact. Increment the inspection generation before enqueueing so stale worker deliveries cannot overwrite a newer result.

When a new task depends on freshly committed Dataset metadata, enqueue it with `transaction.on_commit()`.

## Frontend

```bash
npm install
npm run build
```

Use the watch scripts from `package.json` while editing Tailwind or JavaScript. Generated `static/css/app.css` and `static/js/app.js` files are build artifacts and remain ignored.

Dataset preview and status refresh use server-rendered HTMX endpoints. Business rules and permission checks must still work without JavaScript.

## Worker

With Redis available at `REDIS_URL`:

```bash
celery -A config worker --loglevel=INFO
```

The deterministic infrastructure task can be used to verify the actual broker/worker/result path. Load Studio's configured Celery application explicitly when using a standalone Python process:

```bash
python -c "from config import celery_app; result = celery_app.send_task('common.health_ping'); print(result.get(timeout=10))"
```

Dataset import inspection is also a real worker workload. Web and worker processes must share access to `DATASET_STORAGE_ROOT` for the current local filesystem backend; Docker Compose mounts the same private volume into both services.

## Scientific implementation rule

Studio code may import documented AgencityLab public APIs through `labbridge`. Dataset code must not call AgencityLab computations at all in Plan 4.

Do not copy formulas, reach into AgencityLab private/core modules, infer `A_ref`, `tau`, `w` or `P_c`, or silently preprocess raw DatasetVersions. Sorting, deletion of points, interpolation, resampling, filtering, smoothing and unit conversion belong to the later Data Preparation and Provenance layer.

See `docs/datasets.md` for the full raw-data, provenance, inspection and permission contract.
