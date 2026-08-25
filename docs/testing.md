# Testing guide

AgencityStudio tests protect application behavior and integration contracts. They do not validate the Theory of Agencity; scientific correctness remains AgencityLab's responsibility.

## Layers

### Unit and Django tests

`pytest` covers authentication, password reset, custom-user creation, automatic personal workspaces, organisation creation, workspace permission policies, Owner invariants, invitation lifecycle/security, Project ownership/lifecycle/duplication, Project permissions/isolation, Dataset ownership/versioning/provenance, raw storage, importers, data-quality inspection, private downloads, explicit Data Preparation transformations/provenance, System scientific-context versioning/provenance, canonical Analysis configuration/execution/result storage, canonical result reading/visualization, health contracts, task lifecycle primitives and the `labbridge` runtime contract.

Local test settings use SQLite for fast isolated behavior tests, Django's in-memory email backend, a fast test password hasher and eager Celery with in-memory backends. Permission policies plus representative endpoints are tested instead of an exhaustive role × URL matrix.

Dataset regression tests focus on invariants that would corrupt or disclose scientific source data: exact-source SHA-256, immutable raw bytes, stable DatasetVersion history, current-version consistency, path confinement, upload limits, import failures, cross-workspace isolation and permission enforcement.

Preparation regression tests focus on source-version pinning, ordered recipes, deterministic transformation behavior, separate recipe/output fingerprints, immutable source bytes, prepared-artifact publication, role separation and cross-workspace isolation.

System regression tests focus on immutable historical revisions, stable per-System revision numbers, current-revision consistency, primary-observable constraints, parameter provenance, explicit-vs-unspecified `w`, known/unknown unit behavior, configuration fingerprints, permissions and private Project/Workspace isolation. They must not execute the Agencity pipeline.

Analysis regression tests focus on exact source/SystemRevision/mapping pinning, run-number uniqueness, terminal immutability, no hidden preprocessing, strict unit representation, explicit-vs-unspecified `w`, result schema/hash integrity, complex dtype preservation, worker idempotence, safe failure semantics and permission/isolation boundaries.

Visualization regression tests focus on read-only schema access, exact series/range/sample values, preservation of complex U/beta/b data, stored Theta, original-index preservation during display decimation, exact full-resolution selected samples, server-paginated original order, artifact SHA-256 immutability, safe JSON, missing/corrupt artifact behavior and Workspace isolation.

### PostgreSQL integration

CI runs the backend suite with `config.settings.ci`, which uses the real PostgreSQL 17 service. CI applies the migration graph explicitly before the test suite. `makemigrations --check --dry-run` prevents model changes without migrations.

PostgreSQL execution is required for identity, membership, Project, Dataset, preparation, System and Analysis relational constraints, including per-Dataset version-number uniqueness, per-System scientific revision-number uniqueness, one primary observable per revision, per-Analysis run-number uniqueness, the exactly-one-source AnalysisRun check and protective ownership relationships. Plan 8 adds no persistent visualization model and therefore no artificial migration.

### Identity and permission security

Blocking regressions include authentication failure, cross-workspace disclosure, privilege escalation, removal/demotion of the final Owner, reusable/expired/revoked invitations, Project/Dataset mutation by read-only roles, Project deletion with retained Datasets/Systems/Analyses, source lineage deletion and migrations that fail against PostgreSQL.

A Django `is_staff` user receives no Workspace, Project, Dataset, preparation, System or Analysis access unless an explicit membership exists. Private object URLs return 404 to non-members. Known members receive 403 for management actions outside their role.

Analysis endpoint tests include non-member 404 for Analysis/Run/rerun routes, Viewer read-only access and Analyst denial for Owner-only hard deletion. Visualization endpoint tests additionally require member access for manifest/series/sample data, non-member 404, private/no-store responses and absence of filesystem/storage paths in browser payloads. DatasetVersion, PreparedDataArtifact and SystemRevision foreign keys used by Runs are protective because reproducibility takes precedence over convenient cascade deletion.

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

### System scientific-context tests

The Plan 6 backend suite verifies the public AgencityLab 1.1.3 input contract without running `compute_agencity`: explicit `A_ref`, `tau` and `w` must be finite and strictly positive, while scalar `P_c` is finite and non-negative, including the valid `P_c=0` case.

Tests preserve the scientific distinction between `w` left unspecified and an explicit `w` numerically equal to `tau`. Known units are dimensionally checked with the shared Pint service; unknown units remain preserved and produce documentation warnings rather than being guessed or coerced to dimensionless.

The critical immutability test creates Revision 1, creates Revision 2 with a changed `tau`, and verifies that Revision 1 retains its original parameters. A deterministic fingerprint test protects canonical serialization of the scientific context while explicitly not treating a matching hash as scientific validation.

### Canonical Analysis equivalence tests

The fundamental Plan 7 test compares the public Lab call directly against the Studio labbridge for the same arrays and exact arguments:

```python
from agencitylab import compute_agencity
from labbridge.execution import execute_canonical_analysis

direct = compute_agencity(...)
through_studio = execute_canonical_analysis(...).result
```

Public arrays are compared directly with tight floating-point tolerances; Studio never constructs expected `J`, `Theta`, `beta`, `b` or other canonical values from duplicated formulas. Representative cases include a deterministic sinusoid, constant signal, valid `P_c=0` and public `w=None` behavior.

Result round-trip tests serialize the public result, reload it and verify names, shape, dtype and exact complex values for `U`, `beta` and `b`. The result SHA-256 is checked against exact serialized bytes. No float/complex downcast is accepted.

Source-contract tests deliberately use non-finite, non-monotonic and irregular coordinates and assert that Studio rejects them without sorting, filling, interpolation or resampling. A dimensionally compatible but differently scaled unit pair is rejected because Analysis does not convert units implicitly.

The omitted-`w` test is especially important: Studio preflight must not replace `w=None` with `tau`. A fixture where the Lab-resolved omitted window is incompatible with `dt` therefore passes Studio's omitted-window preflight and is rejected by AgencityLab in the worker. The Run must become `FAILED` with `LAB_VALIDATION_ERROR` and no result artifact.

### Canonical visualization tests

Plan 8 tests use the immutable Plan 7 artifact or a real Lab-backed Run as the reference. They never implement expected canonical formulas in Studio test code.

The reader contract verifies that manifest metadata, an exact stored series, an exact first-axis range and one exact sample all match the stored NumPy data. Complex tests compare shape, dtype, real and imaginary components for `U`, `beta` and `b` before checking browser transport representations.

The critical Theta regression deliberately uses a Lab-backed result where `arg(beta)` differs from stored `theta` for at least one sample. The test compares the visualization response directly with the stored Lab `theta` array. It does **not** recalculate Theta from M/O or any copied formula. This blocks the scientifically incorrect substitution `Theta = angle(beta)`.

Display-decimation tests verify that bounded chart payloads preserve original sample indices and range endpoints. Selecting an index from a decimated response must then return the exact full-resolution sample. The artifact file SHA-256 and database `result_sha256` must be unchanged before and after exploration.

Exact-table tests verify original sample order and exact complex components. No test expects sorting by scientific value because such a UI feature would be misleading.

Missing result files and reader failures must produce explicit unavailable/integrity states without an automatic AgencityLab rerun. Cross-workspace visualization requests must resolve as 404 before numerical data are disclosed.

### AgencityLab integration

The test suite imports the documented AgencityLab package root and verifies that the installed version matches Studio's pinned compatibility version. Studio tests must not import AgencityLab private/core modules.

`labbridge.scientific_context` inspects the public `compute_agencity` signature. `labbridge.execution` is the only canonical execution adapter and captures public warnings/exceptions without changing inputs or results. Plan 8 visualization code must not import or call it.

### Browser smoke tests

Playwright runs Chromium critical flows on pull requests, including account/workspace/Project paths, the raw Dataset workflow, one real prepared-data workflow, Plan 6 System flows, one real Plan 7 canonical Analysis flow and one Plan 8 canonical Results exploration flow.

The canonical Analysis browser path remains end to end:

```text
login/signup
→ Project
→ import uniform numeric CSV
→ annotate Time/Observable + units
→ create explicit PreparedDataArtifact when that workflow is under test
→ define documented SystemRevision
→ Analyses / New Analysis
→ choose exact source
→ map coordinate and observable
→ choose exact SystemRevision + ObservableDefinition
→ Review A_ref / tau / w / P_c and engine
→ Run Analysis
→ real Redis/Celery worker
→ public AgencityLab compute_agencity
→ wait for COMPLETED
→ inspect private result availability and reproducibility
```

The Plan 8 browser test then opens the immutable result and traverses Overview, Observable, Dynamics, Structure, Contrast & Orientation, Agencity State, Agencity Flux, Exact table and Reproducibility. It verifies real chart initialization, U/beta/b complex-plane presence, selected-sample persistence and theme adaptation.

Sample synchronization is tested through accessible Previous/Next/direct-index controls rather than arbitrary canvas pixel coordinates. This protects the scientific state transition while avoiding a fragile rendering-coordinate test. Complex-plane rendering itself receives a smoke assertion that the chart initialized successfully.

The prepared-data workflow remains separately tested for recipe/provenance behavior. The System workflow remains separately tested for immutable revision history. A malformed XLSX browser scenario verifies a friendly FAILED state without exposing a raw parser traceback.

Selectors use accessible labels/roles rather than pixel snapshots or arbitrary sleeps. Async tests wait for real READY/COMPLETED/FAILED states rather than `waitForTimeout()`. Pixel-perfect screenshot comparisons are deliberately not blocking tests.

### Container integration

The Docker CI job builds application images, starts PostgreSQL and Redis, applies migrations, starts web and Celery worker processes, waits for `/health/ready/`, and executes `common.health_ping` through the actual broker/worker/result path.

Web and worker mount the same private storage volume used by raw, prepared and canonical result artifacts. This is required so asynchronous workers can read pinned sources and publish results visible to the web process. Visualization adds no new infrastructure service and does not change readiness dependencies.

The Docker frontend build must contain the locally bundled ECharts Results asset while ordinary pages continue to use the normal global app bundle.

## Commands

```bash
pytest
ruff check accounts analyses config common datasets labbridge projects systems workspaces tests
npm run build
npm run test:e2e
```

For the CI-shaped PostgreSQL backend suite, provide the PostgreSQL environment variables and run:

```bash
DJANGO_SETTINGS_MODULE=config.settings.ci pytest
```

For the full deployment-shaped path, use Docker Compose as documented in the README.

Do not weaken a failing test that reveals wrong bytes, wrong source version, wrong SystemRevision, wrong mapping, permission leakage, source/result mutation, hidden preprocessing, complex result corruption, lost parameter provenance, cross-workspace access, Theta/arg(beta) confusion, wrong sample synchronization, a 500 response or direct-Lab/Studio numerical divergence. Conversely, avoid blocking development on exact chart pixels, minor line thickness, icon placement, tooltip punctuation, animation duration or cosmetic timing assertions.
