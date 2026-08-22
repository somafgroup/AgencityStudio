# Development guide

The repository is designed so contributors can work through Docker Compose or run the Django/frontend processes directly while PostgreSQL and Redis remain external services.

## Environment

Copy `.env.example` to `.env` for Docker Compose. The example is development-only; never reuse its secret or database password in production.

Important variables:

- `DJANGO_SETTINGS_MODULE`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
- `REDIS_URL`

Production additionally supports `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_SECURE_SSL_REDIRECT` and the `DJANGO_SECURE_HSTS_*` settings.

## Python

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e . pytest pytest-django ruff
python manage.py migrate
pytest
ruff check config common labbridge tests
```

AgencityLab is installed through Studio's pinned runtime dependency. Do not install a different Lab version silently to make a Studio workflow pass; update the explicit compatibility contract in a dedicated change when a new Lab release is adopted.

## Frontend

```bash
npm install
npm run build
```

Use the watch scripts from `package.json` while editing Tailwind or JavaScript. Generated `static/css/app.css` and `static/js/app.js` files are build artifacts and remain ignored.

## Worker

With Redis available at `REDIS_URL`:

```bash
celery -A config worker --loglevel=INFO
```

The deterministic infrastructure task can be used to verify the actual broker/worker/result path. Load Studio's configured Celery application explicitly when using a standalone Python process:

```bash
python -c "from config import celery_app; result = celery_app.send_task('common.health_ping'); print(result.get(timeout=10))"
```

## Scientific implementation rule

Studio code may import documented AgencityLab public APIs through `labbridge`. Do not copy formulas, reach into AgencityLab private/core modules, or infer physical parameters inside the UI layer.
