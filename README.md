# AgencityStudio

AgencityStudio is the Web interface and orchestration layer for AgencityLab. It provides a browser-based scientific workspace while keeping all Agencity mathematics inside the AgencityLab public API.

## Current foundation

- Django 5.2 application served through ASGI/Uvicorn.
- PostgreSQL persistence.
- Redis-backed Celery worker execution.
- AgencityLab 1.1.3 pinned as the scientific runtime dependency.
- Server-rendered templates with Tailwind CSS, HTMX and Alpine.js.
- Light, dark and system themes.
- Playwright smoke coverage for the visible application shell.
- Docker Compose development/runtime stack.
- Liveness at `/health/` and dependency readiness at `/health/ready/`.

## Scientific boundary

Studio must never reproduce canonical equations or reach into private AgencityLab internals. Scientific computation enters through `labbridge`, which imports the documented AgencityLab package surface. The pinned runtime contract is currently AgencityLab `1.1.3`.

## Quick start with Docker Compose

```bash
cp .env.example .env
docker compose build
docker compose up -d postgres redis
docker compose run --rm web python manage.py migrate --noinput
docker compose up -d web worker
```

Open `http://localhost:8000/`.

The readiness endpoint should return HTTP 200 once PostgreSQL, Redis and the compatible AgencityLab runtime are available:

```bash
curl http://localhost:8000/health/ready/
```

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

The CI pipeline checks Python quality, Django configuration, production settings, migration consistency, backend tests, frontend build, Playwright, Docker image construction, Compose readiness and an actual Celery task round trip.

Additional documentation lives under `docs/`, especially `docs/architecture.md`, `docs/development.md`, `docs/testing.md` and `docs/ui.md`.
