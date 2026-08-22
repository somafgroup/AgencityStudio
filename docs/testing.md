# Testing guide

AgencityStudio tests protect application behavior and integration contracts. They do not validate the Theory of Agencity; scientific correctness remains AgencityLab's responsibility.

## Layers

### Unit and Django tests

`pytest` covers URL/view behavior, health contracts, UI rendering, task lifecycle primitives and the `labbridge` runtime contract. Test settings use SQLite for fast isolated tests and run Celery eagerly with in-memory backends.

### PostgreSQL integration

CI runs Django checks and applies the real migration graph against PostgreSQL 17 before running the test suite. `makemigrations --check --dry-run` prevents accidental model changes without migrations.

### AgencityLab integration

The test suite imports the documented AgencityLab package root and verifies that the installed version matches Studio's pinned compatibility version. Studio tests must not import AgencityLab private/core modules.

### Browser smoke tests

Playwright exercises meaningful shell workflows: application load, primary navigation, command palette, persisted theme and mobile navigation. Avoid tests for visual trivia that is already covered by lower-cost rendering tests.

### Container integration

The Docker CI job builds the application images, starts PostgreSQL and Redis, applies migrations, starts both the web process and Celery worker, waits for `/health/ready/`, and executes `common.health_ping` through the actual broker/worker/result path.

## Commands

```bash
pytest
ruff check config common labbridge tests
npm run build
npm run test:e2e
```

For the full deployment-shaped path, use Docker Compose as documented in the README.
