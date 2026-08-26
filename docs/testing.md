# Testing guide

AgencityStudio tests protect software behavior, provenance, isolation and integration contracts. They do **not** claim to validate the Theory of Agencity. Scientific numerical authority remains AgencityLab.

## Test layers

The repository combines:

- Ruff and Python compilation;
- Django system and production checks;
- migration consistency and real PostgreSQL migrations;
- PostgreSQL-backed pytest suites;
- direct AgencityLab ↔ Studio equivalence tests;
- Chromium Playwright workflows;
- Docker Compose build/readiness checks;
- Redis/Celery worker round trips.

## Canonical tests

Canonical tests compare Studio's public `labbridge.execution` path with direct public `agencitylab.compute_agencity` on the same explicit inputs. Expected scientific arrays are not reconstructed from Studio formulas.

They also protect:

- exact source and SystemRevision pinning;
- canonical result SHA-256 and execution fingerprint provenance;
- complex dtype preservation;
- unspecified `w` handling;
- `P_c = 0` support;
- immutable result artifacts;
- private Workspace-scoped access;
- stored canonical `theta` independently of display phase.

## Plan 9 diagnostic equivalence

The fundamental diagnostic test uses the exact same immutable canonical result for both paths:

```text
direct public AgencityLab analyze_agencity
vs
Studio -> labbridge.diagnostics -> public analyze_agencity
```

Studio does not compute a golden coherence, variance, curvature, winding or real-agencity answer itself.

The Plan 9 regression suite protects at least:

- public diagnostic bundle equivalence;
- stored canonical `theta` supplied to the public `AgencityResult` container;
- a fixture where `Theta != arg(beta)`;
- no Studio-invented interpretive threshold in default configuration;
- exact transmission and persistence of explicit user diagnostic thresholds;
- honest `undetermined`/empty/no-detection outcomes;
- canonical result SHA-256 unchanged after diagnostics;
- deterministic diagnostic fingerprinting;
- immutable completed `DiagnosticRun` and `DiagnosticResultArtifact`;
- changed configuration creating a new DiagnosticRun rather than rewriting history;
- canonical hash mismatch blocking diagnostic execution;
- Analyst run permission, Viewer read-only behavior and non-member 404 isolation;
- strict artifact serialization including non-finite Lab diagnostic values;
- duplicate worker delivery not publishing competing artifacts.

Warnings produced by the public Lab/NumPy diagnostic path may accompany a completed run. A warning is not automatically a test failure or a reason to modify the scientific contract.

## Real worker coverage

Diagnostic execution is a real Celery workload. The test suite checks task registration, while Playwright exercises the production-shaped path:

```text
DiagnosticRun QUEUED
  -> Redis
  -> Celery worker
  -> public AgencityLab diagnostic API
  -> immutable diagnostic artifact
  -> COMPLETED
```

The worker module `analyses.diagnostic_tasks` is explicitly registered with Celery. This is covered because a task that only works when called directly in pytest is insufficient evidence that the real worker can consume it.

Scientific validation/configuration errors are expected to become safe failed runs rather than uncontrolled retries.

## Playwright

Playwright covers user workflows, not every numeric diagnostic permutation. The Plan 9 path covers:

```text
login
-> completed canonical AnalysisRun
-> Diagnostics
-> configure
-> Review
-> Run
-> real worker completion
-> Diagnostic Workspace
-> canonical/diagnostic distinction
-> diagnostic chart
-> exact shared sample selection
-> provenance / real-agencity view
```

Backend tests carry the combinatorial burden for roles, thresholds and scientific-output contracts. E2E tests intentionally avoid pixel-perfect chart assertions and fragile canvas coordinate clicks.

## Negative outcomes

A test must not force a positive scientific label simply because a fixture is sinusoidal, stochastic or chaotic. Assertions should follow the public Lab contract.

Valid outcomes include:

- no detected event;
- empty segment collection;
- unknown or unclassified regime;
- `undetermined` real-agencity assessment;
- completed result with warnings.

Tests must never change `beta`, `J`, `D`, `S`, `Theta`, `tau`, `w`, `A_ref` or `P_c` merely to obtain an attractive classification.

## Threshold tests

Any diagnostic threshold appearing in production code must be traceable to one of:

- explicit user configuration;
- a public Lab diagnostic default/contract;
- numerical/validation safety;
- a test fixture value.

Threshold test values are not theory constants. The default Studio configuration intentionally leaves contextual interpretive thresholds absent where Lab permits absence.

## Security and isolation

Blocking regressions include:

- cross-Workspace diagnostic detail access;
- cross-Workspace artifact/visualization access;
- Viewer escalation to diagnostic execution;
- canonical run/hash mismatch;
- public storage URLs or leaked backend paths;
- mutation of historical canonical or diagnostic artifacts.

## CI acceptance

A Plan 9 change is not complete merely because focused tests pass. Required CI should remain healthy through PostgreSQL, Playwright and Docker/Compose readiness. Report only counts and statuses actually observed from CI logs.

The key scientific CI rule is: Studio must reproduce the **AgencityLab public diagnostic software contract**, not prove the underlying theory.