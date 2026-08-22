# Testing guide

AgencityStudio tests protect application behavior and integration contracts. They do not validate the Theory of Agencity; scientific correctness remains AgencityLab's responsibility.

## Layers

### Unit and Django tests

`pytest` covers authentication, password reset, custom-user creation, automatic personal workspaces, organisation creation, workspace permission policies, Owner invariants, invitation lifecycle/security, URL isolation, UI rendering, health contracts, task lifecycle primitives and the `labbridge` runtime contract.

Test settings use SQLite for fast isolated behavior tests, Django's in-memory email backend, a fast test password hasher and eager Celery with in-memory backends. Permission policies plus representative endpoints are tested instead of an exhaustive role × URL matrix.

### PostgreSQL integration

CI runs Django checks and applies the real migration graph against PostgreSQL 17 before the Python suite. `makemigrations --check --dry-run` prevents model changes without migrations. This PostgreSQL migration step is required for Plan 2 because conditional uniqueness, functional email uniqueness and membership constraints must not rely on SQLite behavior alone.

### Identity and permission security

Blocking regressions include authentication failure, broken reset links, cross-workspace disclosure, privilege escalation, removal/demotion of the final Owner, reusable/expired/revoked invitations and migrations that fail against PostgreSQL. A Django `is_staff` user receives no workspace access unless an explicit membership exists.

Private workspace URLs are tested to return 404 to a non-member. Known members receive 403 for management actions outside their role.

### AgencityLab integration

The test suite imports the documented AgencityLab package root and verifies that the installed version matches Studio's pinned compatibility version. Studio tests must not import AgencityLab private/core modules.

### Browser smoke tests

Playwright runs Chromium critical flows on pull requests:

- signup → personal workspace → logout → login;
- organisation workspace creation → members page;
- invitation email → invited signup/acceptance → membership;
- Viewer can view a workspace but receives an access-denied response for member management;
- existing navigation, command palette, persisted theme and mobile navigation.

Selectors use accessible labels/roles rather than pixel snapshots or timing sleeps.

### Container integration

The Docker CI job builds the application images, starts PostgreSQL and Redis, applies migrations, starts both the web process and Celery worker, waits for `/health/ready/`, and executes `common.health_ping` through the actual broker/worker/result path.

## Commands

```bash
pytest
ruff check accounts config common labbridge workspaces tests
npm run build
npm run test:e2e
```

For the full deployment-shaped path, use Docker Compose as documented in the README.
