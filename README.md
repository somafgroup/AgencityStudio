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
- Server-side Dataset preview, column roles/units, quality findings and version history.
- Explicit Data Preparation recipes pinned to an exact DatasetVersion.
- Immutable prepared artifacts with separate SHA-256, software provenance and prepared-data inspection.
- Explicit crop, row exclusion, missing-value treatment, linear interpolation, resampling, moving-average smoothing, compatible unit conversion, column selection and time sorting.
- Project-owned Systems with stable UUID identities and immutable scientific revisions.
- Explicit observable definitions, units, `A_ref`, `tau`, `w`, `P_c`, parameter origins, justifications and scientific references.
- Light, dark and system themes.
- Chromium Playwright coverage for shell, account, workspace, invitation, Project, Dataset, preparation, System and permission workflows.
- Docker Compose development/runtime stack.
- Liveness at `/health/` and dependency readiness at `/health/ready/`.

## Scientific boundary

Studio must never reproduce canonical equations or reach into private AgencityLab internals. Scientific computation enters through `labbridge`, which imports the documented AgencityLab package surface. The pinned runtime contract is currently AgencityLab `1.1.3`.

Identity, workspace and Project permissions are application concerns. Dataset inspection describes source data and data quality; it does not infer `A_ref`, `tau`, `w` or `P_c`, and it performs no Agencity calculation. Raw DatasetVersions are never silently sorted, filtered, interpolated, resampled, normalized or otherwise preprocessed.

Plan 5 adds a separate explicit preparation layer. A user may request defined transformations, which produce a new immutable prepared artifact while preserving the original DatasetVersion. Sampling interval `dt` used for resampling remains distinct from physical `tau` and CRM window `w`.

Plan 6 adds a separate scientific-context layer. A SystemRevision documents observables and physical/contextual `A_ref`, `tau`, `w` and `P_c` with units, origins and justifications. Studio does not derive these values from signal statistics, acquisition `dt`, a spectrum, autocorrelation or any other signal-derived heuristic. `w` left unspecified remains distinct from explicitly setting `w = tau`. No Agencity computation occurs in the Systems workspace.

Frequency filtering remains deliberately deferred until a precise sampling/cutoff/order/phase/anti-alias contract is implemented. Studio does not introduce hidden filter defaults merely to expose another preprocessing option.

## Quick start with Docker Compose

```bash
cp .env.example .env
docker compose build
docker compose up -d postgres redis
docker compose run --rm web python manage.py migrate --noinput
docker compose up -d web worker
```

Open `http://localhost:8000/`, create a local account and AgencityStudio will create its private personal workspace. Projects organise the scientific work. The Data Workspace can import immutable raw sources, the Prepare tab can materialize explicit derived views, and the Systems tab documents versioned scientific context independently from those data artifacts.

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

Dataset/preparation storage is protected by configurable instance limits:

```text
DATASET_MAX_UPLOAD_BYTES=<bytes>
DATASET_MAX_PASTE_BYTES=<bytes>
DATASET_STORAGE_ROOT=<private path>
DATA_PREPARATION_MAX_ROWS=<rows>
```

`DATA_PREPARATION_MAX_ROWS` is an implementation memory-safety bound for the current in-memory transformation engine. It is not a scientific threshold.

See `docs/accounts-and-workspaces.md` for identity/workspace semantics, `docs/datasets.md` for raw Dataset contracts, `docs/data-preparation.md` for prepared-data lineage and transformations, and `docs/systems.md` for scientific System revisions and physical/contextual parameter provenance.

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

The CI pipeline checks Python quality, Django configuration, production settings, migration consistency, PostgreSQL migrations, backend identity/workspace/Project/Dataset/preparation/System permission and provenance tests, frontend build, critical Playwright flows, Docker image construction, Compose readiness and an actual Celery task round trip.

Additional documentation lives under `docs/`, especially `docs/architecture.md`, `docs/accounts-and-workspaces.md`, `docs/projects.md`, `docs/datasets.md`, `docs/data-preparation.md`, `docs/systems.md`, `docs/development.md`, `docs/testing.md` and `docs/ui.md`.
