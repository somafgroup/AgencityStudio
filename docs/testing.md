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

They also protect exact source/SystemRevision pinning, complex dtype preservation, unspecified `w`, `P_c = 0`, immutable artifacts, private access and stored canonical `theta`.

## Plan 9 diagnostic equivalence

The fundamental diagnostic test uses the exact same immutable canonical result for both paths:

```text
direct public AgencityLab analyze_agencity
vs
Studio -> labbridge.diagnostics -> public analyze_agencity
```

Studio does not compute a golden coherence, variance, curvature, winding or real-agencity answer itself.

The Plan 9 regression suite protects public bundle equivalence, stored canonical `theta`, `Theta != arg(beta)`, threshold provenance, honest negative outcomes, immutable canonical/diagnostic artifacts, deterministic fingerprints, role isolation, safe non-finite serialization and duplicate worker delivery.

Warnings produced by the public Lab/NumPy diagnostic path may accompany a completed run. A warning is not automatically a test failure or a reason to modify the scientific contract.

## Plan 10 multiscale/window equivalence

Plan 10 adds two direct public-API comparisons.

Tau multiscale:

```text
direct agencitylab.api.compute_agencity_spectrum
vs
Studio -> labbridge.sensitivity -> compute_agencity_spectrum
```

The same `u`, `xi`, exact tau grid, `A_ref`, `P_c` and window request are supplied. Tests compare Lab-returned scale arrays, effective windows, complex `b`/`beta` spectra and summary arrays. No Studio formula is used as a golden value.

Window sensitivity:

```text
direct agencitylab.api.optimize_agencity_window
vs
Studio -> labbridge.sensitivity -> optimize_agencity_window
```

The same fixed `tau`, `A_ref`, `P_c` and explicit window candidates are supplied. Tests compare `candidate_w`, `phi2`, `phi1_mean_abs_contrast`, eligibility, `best_index`, criterion and `w_opt` exactly according to the public Lab contract.

Critical Plan 10 regressions include:

- `w=UNSPECIFIED` remains `None` at the Studio/Lab boundary during a tau sweep;
- Lab-returned effective `w` is recorded separately rather than invented by Studio;
- an explicit base `w` remains fixed during a tau sweep;
- a window study varies `w` while keeping `tau` fixed;
- `P_c=0` remains legal when the public Lab API accepts it;
- invalid non-grid-aligned `w` candidates are rejected instead of rounded;
- explicit/linear/log grids are deterministic and their exact values are persisted;
- a changed grid changes the sensitivity execution fingerprint;
- no study mutates `SystemRevision.tau`, `SystemRevision.w`, the canonical Run, source hash or canonical result hash;
- the canonical result artifact bytes remain unchanged after sensitivity execution;
- complex multiscale arrays survive ZIP/NPY storage without dtype loss;
- duplicate Celery delivery produces one authoritative result artifact;
- Analyst can create/run studies, Viewer is read-only and non-members receive 404 on result endpoints;
- no test asserts that a numerical maximum is a physical `tau` or that `w_opt` is the true physical memory.

## Real worker coverage

Canonical, diagnostic and sensitivity execution are real Celery workloads. The Plan 10 Playwright path exercises:

```text
SensitivityStudy QUEUED
  -> Redis
  -> Celery worker
  -> public AgencityLab multiscale API
  -> immutable sensitivity artifact
  -> COMPLETED
```

Only a study UUID is sent through Redis. A direct task call alone is not sufficient; the E2E worker path proves task discovery and shared-storage behavior.

Scientific validation/configuration errors are expected to become safe failed studies rather than uncontrolled retries.

## Playwright

Playwright covers user workflows, not every numeric permutation. The integrated scientific path now covers:

```text
login
-> prepare data
-> completed canonical AnalysisRun
-> Tau multiscale SensitivityStudy
-> Review exact grid/fixed context
-> real worker completion
-> ECharts sensitivity view + exact table
-> Diagnostics
-> real diagnostic worker completion
-> Diagnostic Workspace
```

Backend tests carry the combinatorial burden for roles, grid types, window candidates and scientific-output contracts. E2E tests intentionally avoid pixel-perfect chart assertions, arbitrary canvas clicks and fixed sleeps.

## Negative/flat outcomes

A test must not force a positive scientific label or preferred scale simply because a fixture is sinusoidal, stochastic or chaotic.

Valid outcomes include diagnostic no-detection/unknown states and sensitivity curves that are flat, unexpected or lack a visually distinctive maximum.

Tests must never change `beta`, `J`, `D`, `S`, `Theta`, `tau`, `w`, `A_ref` or `P_c` merely to obtain an attractive classification or spectrum.

## Threshold and grid tests

Any diagnostic threshold appearing in production code must be traceable to explicit user configuration, a public Lab contract, numerical safety or a test fixture.

Sensitivity grid values are user/study configuration, not theory constants. `SENSITIVITY_MAX_POINTS` is an operational guard only. Tests must ensure Studio rejects an oversized request rather than silently truncating it.

## Security and isolation

Blocking regressions include cross-Workspace canonical/diagnostic/sensitivity result access, Viewer escalation, mismatched pinned hashes, public storage URLs, leaked backend paths and mutation of historical artifacts.

## CI acceptance

Plan 10 is not complete merely because focused tests pass. Required CI must remain healthy through PostgreSQL, Playwright and Docker/Compose readiness. Report only counts and statuses actually observed from CI logs.

The key scientific CI rule is: Studio must reproduce the **AgencityLab public canonical, diagnostic and sensitivity software contracts** for identical inputs. The tests do not prove the underlying theory or automatically validate a physical parameter from a numerical optimum.
