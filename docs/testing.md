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

## Plan 12 observable-field equivalence

Plan 12 adds an **EXPERIMENTAL** observable spatial field path. Its blocking scientific-software tests compare identical inputs in two ways:

```text
direct agencitylab.fields.compute_agencity_field
vs
Studio -> labbridge.fields -> compute_agencity_field
```

and, at selected spatial locations:

```text
field result at one spatial point
vs
direct public agencitylab.compute_agencity on that local temporal series
```

The field fixtures cover one- and two-dimensional space, a non-zero `time_axis`, explicit spatial coordinates, scalar and spatial `A_ref`/`tau`, `w=None`, explicit spatial `w`, scalar/spatial/space-time `P_c`, local `P_c=0`, wrong map shapes, exact N-D indexing, immutable NPZ source bytes, private Workspace access and lossless complex `beta_obs`/`b_obs` serialization. CRM-window fixtures obey the public Lab sampling contract; tests never make Studio round or alter a physical parameter to obtain a pass.

There is no Studio-side golden field equation. Tests fail if Studio changes axes, reshapes data silently, changes `w=None`, corrupts a map, loses complex dtype/shape, returns the wrong exact cell or leaks a field result across Workspaces.

## Real worker coverage

Canonical, diagnostic, sensitivity and observable-field execution are real Celery workloads. The Plan 12 Playwright path exercises a small immutable NPZ field through:

```text
AnalysisRun QUEUED
  -> Redis
  -> Celery worker
  -> public compute_agencity_field
  -> immutable field result artifact
  -> COMPLETED
```

Only a Run UUID is sent through Redis. The E2E path then opens the EXPERIMENTAL field workspace, changes the selected time, selects an exact spatial position, inspects the local trace and verifies reproducibility information.

Scientific validation/configuration errors are expected to become safe failed records rather than uncontrolled retries.

## Playwright

Playwright covers user workflows, not every numeric permutation. Backend tests carry the combinatorial burden for roles, dimensions, axis orders and parameter modes. E2E tests intentionally avoid pixel-perfect chart assertions, arbitrary canvas clicks and fixed sleeps.

## Negative/flat outcomes

A test must not force a positive scientific label or preferred scale simply because a fixture is sinusoidal, stochastic or chaotic.

Valid outcomes include diagnostic no-detection/unknown states, sensitivity curves that are flat or unexpected, and observable fields whose local `beta_obs` or `b_obs` values do not support any coherence claim.

Tests must never change `beta`, `J`, `D`, `S`, `Theta`, `tau`, `w`, `A_ref` or `P_c` merely to obtain an attractive classification, spectrum or spatial map.

## Threshold, grid and field-operation tests

Any diagnostic threshold appearing in production code must be traceable to explicit user configuration, a public Lab contract, numerical safety or a test fixture.

Sensitivity grid values are user/study configuration, not theory constants. Field upload/element/display limits are operational guards only. Tests must ensure Studio rejects oversized requests rather than silently truncating scientific data.

Plan 12 tests and code review additionally protect the absence of spatial CRM, spatial derivatives, automatic spatial averaging, interpolation, resampling, smoothing, normalization and signal-derived physical parameter maps.

## Security and isolation

Blocking regressions include cross-Workspace canonical/diagnostic/sensitivity/field result access, Viewer escalation, mismatched pinned hashes, public storage URLs, leaked backend paths and mutation of historical artifacts.

## CI acceptance

Plan 12 is not complete merely because focused tests pass. Required CI must remain healthy through PostgreSQL, Playwright and Docker/Compose readiness. Report only counts and statuses actually observed from CI logs.

The key scientific CI rule is: Studio must reproduce the corresponding **AgencityLab public software contract** for identical inputs. The tests do not prove the underlying theory, validate autonomous field physics, or automatically validate a physical parameter from a numerical result.
