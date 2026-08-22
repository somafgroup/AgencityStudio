# Testing guide

AgencityStudio tests protect application behavior and integration contracts. They do not validate the Theory of Agencity; scientific correctness remains AgencityLab's responsibility.

## Layers

### Unit and Django tests

`pytest` covers authentication, password reset, custom-user creation, automatic personal workspaces, organisation creation, workspace permission policies, Owner invariants, invitation lifecycle/security, Project ownership/lifecycle/duplication, Project permissions and isolation, Dataset ownership/versioning/provenance, raw storage, importers, data-quality inspection, private downloads, health contracts, task lifecycle primitives and the `labbridge` runtime contract.

Local test settings use SQLite for fast isolated behavior tests, Django's in-memory email backend, a fast test password hasher and eager Celery with in-memory backends. Permission policies plus representative endpoints are tested instead of an exhaustive role × URL matrix.

Dataset regression tests focus on invariants that would corrupt or disclose scientific source data: exact-source SHA-256, immutable raw bytes, stable DatasetVersion history, current-version consistency, path confinement, upload limits, import failures, cross-workspace isolation and permission enforcement.

### PostgreSQL integration

CI runs the same backend suite with `config.settings.ci`, which preserves fast test email/password behavior but replaces SQLite with the real PostgreSQL 17 service. CI applies the migration graph explicitly before the test suite. `makemigrations --check --dry-run` prevents model changes without migrations.

PostgreSQL execution is required for identity, membership, Project and Dataset relational constraints, including per-Dataset version-number uniqueness and the protective Project → Dataset relationship.

### Identity, permission and Dataset security

Blocking regressions include authentication failure, cross-workspace disclosure, privilege escalation, removal/demotion of the final Owner, reusable/expired/revoked invitations, Project/Dataset mutation by read-only roles, Project deletion with retained Datasets and migrations that fail against PostgreSQL.

A Django `is_staff` user receives no Workspace, Project or Dataset access unless an explicit membership exists. Private Workspace/Project/Dataset URLs return 404 to non-members. Known members receive 403 for management actions outside their role.

The critical Dataset download test verifies that a user from another Workspace cannot receive source bytes even if they can guess a Dataset or DatasetVersion UUID.

### Importer and inspection tests

Backend tests cover the supported Plan 4 formats rather than multiplying equivalent browser scenarios:

- CSV;
- TSV;
- custom-delimiter structured TXT;
- XLSX sheet selection;
- malformed XLSX failure;
- pasted tabular text.

Inspection tests cover missing values, non-finite values, non-numeric Observable candidates, duplicate/non-monotonic time and irregular observed sampling. These tests assert inspection contracts only; they must never add expectations for inferred `A_ref`, `tau`, `w` or `P_c`.

### AgencityLab integration

The test suite imports the documented AgencityLab package root and verifies that the installed version matches Studio's pinned compatibility version. Studio tests must not import AgencityLab private/core modules. The Data Workspace adds no scientific computation path.

### Browser smoke tests

Playwright runs Chromium critical flows on pull requests, including the existing account/workspace/Project paths and the main Dataset workflow:

```text
login/signup
→ open Project
→ Import Dataset
→ upload small CSV
→ wait for real worker status
→ Preview
→ annotate Time/Observable columns and units
→ inspect Quality
→ confirm current version
→ verify source provenance/download
```

A secondary browser scenario verifies that a malformed XLSX reaches a friendly FAILED state without exposing a raw parser traceback.

Selectors use accessible labels/roles rather than pixel snapshots or arbitrary sleeps. Async Dataset tests wait for real visible/network state rather than `waitForTimeout()`.

### Container integration

The Docker CI job builds application images, starts PostgreSQL and Redis, applies migrations, starts web and Celery worker processes, waits for `/health/ready/`, and executes `common.health_ping` through the actual broker/worker/result path.

Web and worker mount the same private Dataset storage volume so asynchronous inspection can read source artifacts created by the web process.

## Commands

```bash
pytest
ruff check accounts config common datasets labbridge projects workspaces tests
npm run build
npm run test:e2e
```

For the CI-shaped PostgreSQL backend suite, provide the PostgreSQL environment variables and run:

```bash
DJANGO_SETTINGS_MODULE=config.settings.ci pytest
```

For the full deployment-shaped path, use Docker Compose as documented in the README.

Do not weaken a failing test that reveals wrong bytes, wrong DatasetVersion, permission leakage, source mutation, a 500 response or a broken import. Conversely, avoid blocking development on exact wording, icon placement or cosmetic timing assertions.
