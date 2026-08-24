# Testing guide

AgencityStudio tests protect application behavior and integration contracts. They do not validate the Theory of Agencity; scientific correctness remains AgencityLab's responsibility.

## Layers

### Unit and Django tests

`pytest` covers authentication, password reset, custom-user creation, automatic personal workspaces, organisation creation, workspace permission policies, Owner invariants, invitation lifecycle/security, Project ownership/lifecycle/duplication, Project permissions/isolation, Dataset ownership/versioning/provenance, raw storage, importers, data-quality inspection, private downloads, explicit Data Preparation transformations/provenance, health contracts, task lifecycle primitives and the `labbridge` runtime contract.

Local test settings use SQLite for fast isolated behavior tests, Django's in-memory email backend, a fast test password hasher and eager Celery with in-memory backends. Permission policies plus representative endpoints are tested instead of an exhaustive role × URL matrix.

Dataset regression tests focus on invariants that would corrupt or disclose scientific source data: exact-source SHA-256, immutable raw bytes, stable DatasetVersion history, current-version consistency, path confinement, upload limits, import failures, cross-workspace isolation and permission enforcement.

Preparation regression tests focus on source-version pinning, ordered recipes, deterministic transformation behavior, separate recipe/output fingerprints, immutable source bytes, prepared-artifact publication, role separation and cross-workspace isolation.

### PostgreSQL integration

CI runs the backend suite with `config.settings.ci`, which uses the real PostgreSQL 17 service. CI applies the migration graph explicitly before the test suite. `makemigrations --check --dry-run` prevents model changes without migrations.

PostgreSQL execution is required for identity, membership, Project, Dataset and preparation relational constraints, including per-Dataset version-number uniqueness and protective source-version relationships.

### Identity and permission security

Blocking regressions include authentication failure, cross-workspace disclosure, privilege escalation, removal/demotion of the final Owner, reusable/expired/revoked invitations, Project/Dataset mutation by read-only roles, Project deletion with retained Datasets, source lineage deletion and migrations that fail against PostgreSQL.

A Django `is_staff` user receives no Workspace, Project, Dataset or preparation access unless an explicit membership exists. Private object URLs return 404 to non-members. Known members receive 403 for management actions outside their role.

The critical raw/prepared download tests verify that a user from another Workspace cannot receive source or derived bytes even if they can guess UUIDs.

### Importer and inspection tests

Backend tests cover supported import formats rather than multiplying equivalent browser scenarios: CSV, TSV, custom-delimiter TXT, XLSX sheet selection, malformed XLSX and pasted text.

Inspection tests cover missing/non-finite values, non-numeric Observable candidates, duplicate/non-monotonic time and irregular observed sampling. These tests assert inspection contracts only; they must never add expectations for inferred `A_ref`, `tau`, `w` or `P_c`.

### Preparation transformation tests

Small deterministic fixtures test the explicit operations retained in Plan 5:

- time/row crop;
- explicit row exclusion;
- missing-row removal and linear interpolation without extrapolation;
- uniform resampling with explicit `dt`;
- moving-average smoothing;
- compatible Pint unit conversion;
- column selection and explicit time sorting.

Tests verify validation such as strictly increasing interpolation/resampling coordinates and rejection of incompatible units. They also assert that preparation never creates or infers `tau`, `w`, `A_ref` or `P_c`.

Frequency filtering is not part of the retained Plan 5 scope, so no fake filter test exists. When filtering is introduced, its sampling, cutoff/order, phase and anti-alias contracts must be tested explicitly.

### AgencityLab integration

The test suite imports the documented AgencityLab package root and verifies that the installed version matches Studio's pinned compatibility version. Studio tests must not import AgencityLab private/core modules. Data preparation adds no Agencity computation path.

### Browser smoke tests

Playwright runs Chromium critical flows on pull requests, including account/workspace/Project paths, the raw Dataset workflow and one real prepared-data workflow:

```text
login/signup
→ open Project
→ import small CSV
→ annotate Time/Observable + units
→ Prepare
→ create draft pinned to source version
→ add explicit crop + missing-value treatment
→ Review & Run
→ wait for real worker READY state
→ inspect source/prepared fingerprints
→ preview materialized result
```

A secondary Dataset browser scenario verifies that malformed XLSX reaches a friendly FAILED state without exposing a raw parser traceback.

Selectors use accessible labels/roles rather than pixel snapshots or arbitrary sleeps. Async tests wait for real visible/network state rather than `waitForTimeout()`.

### Container integration

The Docker CI job builds application images, starts PostgreSQL and Redis, applies migrations, starts web and Celery worker processes, waits for `/health/ready/`, and executes `common.health_ping` through the actual broker/worker/result path.

Web and worker mount the same private Dataset storage volume, which is also the storage boundary for prepared artifacts. This is required so asynchronous import/preparation workers can read source artifacts and publish prepared results visible to the web process.

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

Do not weaken a failing test that reveals wrong bytes, wrong source version, permission leakage, source mutation, wrong transformation output, lost provenance, a 500 response or a broken import/preparation. Conversely, avoid blocking development on exact wording, icon placement or cosmetic timing assertions.
