# Testing guide

AgencityStudio tests protect application behavior and integration contracts. They do not validate the Theory of Agencity; scientific correctness remains AgencityLab's responsibility.

## Layers

### Unit and Django tests

`pytest` covers authentication, password reset, custom-user creation, automatic personal workspaces, organisation creation, workspace permission policies, Owner invariants, invitation lifecycle/security, Project ownership/lifecycle/duplication, Project permissions and isolation, URL isolation, UI rendering, health contracts, task lifecycle primitives and the `labbridge` runtime contract.

Local test settings use SQLite for fast isolated behavior tests, Django's in-memory email backend, a fast test password hasher and eager Celery with in-memory backends. Permission policies plus representative endpoints are tested instead of an exhaustive role × URL matrix.

### PostgreSQL integration

CI runs the same backend suite with `config.settings.ci`, which preserves the fast test email/password/Celery behavior but replaces SQLite with the real PostgreSQL 17 service. CI also applies the migration graph explicitly before the test suite. `makemigrations --check --dry-run` prevents model changes without migrations. PostgreSQL execution is required for identity, membership and Project relational constraints.

### Identity, permission and Project security

Blocking regressions include authentication failure, broken reset links, cross-workspace disclosure, privilege escalation, removal/demotion of the final Owner, reusable/expired/revoked invitations, Project mutation by read-only roles, workspace deletion cascading through Projects and migrations that fail against PostgreSQL. A Django `is_staff` user receives no workspace or Project access unless an explicit membership exists.

Private workspace and Project URLs are tested to return 404 to a non-member. Known members receive 403 for management actions outside their role.

### AgencityLab integration

The test suite imports the documented AgencityLab package root and verifies that the installed version matches Studio's pinned compatibility version. Studio tests must not import AgencityLab private/core modules. Plan 3 adds no scientific calculation path.

### Browser smoke tests

Playwright runs Chromium critical flows on pull requests:

- signup → personal workspace → logout → login;
- organisation workspace creation → members page;
- invitation email → invited signup/acceptance → membership;
- Viewer can view a workspace but receives an access-denied response for member management;
- Project create → edit → archive → archived list → restore → activity;
- invited Viewer can open a Project but cannot reach Project settings;
- existing navigation, command palette, persisted theme and mobile navigation.

Selectors use accessible labels/roles rather than pixel snapshots or timing sleeps.

### Container integration

The Docker CI job builds the application images, starts PostgreSQL and Redis, applies migrations, starts both the web process and Celery worker, waits for `/health/ready/`, and executes `common.health_ping` through the actual broker/worker/result path.

## Commands

```bash
pytest
ruff check accounts config common labbridge projects workspaces tests
npm run build
npm run test:e2e
```

For the CI-shaped PostgreSQL backend suite, provide the PostgreSQL environment variables and run:

```bash
DJANGO_SETTINGS_MODULE=config.settings.ci pytest
```

For the full deployment-shaped path, use Docker Compose as documented in the README.
