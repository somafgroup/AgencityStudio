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

## Plan 13 Research-field equivalence

Plan 13 adds a distinct **RESEARCH** autonomous-field path. Every scientific module integrated by Studio is tested against the same direct public AgencityLab 1.2.0 call.

Autonomous dynamics:

```text
direct agencitylab.fields.simulate_klein_gordon / simulate_dissipative_klein_gordon / simulate_tdgl
vs
Studio -> labbridge.research -> same public solver
```

The tests compare exact `times`, `phi`, optional `phi_dot`, spatial shape/axes, dynamics name, boundary name, scientific status and solver metadata. Boundary mapping covers Periodic, Dirichlet and Neumann public objects and includes a fixture where changing the boundary changes the Lab result.

The explicit observable→autonomous bridge compares direct `agencitylab.fields.beta_to_phi` with Studio's bridge adapter and uses a scale where the result is demonstrably not the original `beta`. This is a regression against any silent `beta_obs = phi` identity.

Coherent-structure initializers compare direct `domain_wall_profile` and `vortex_field` outputs with the Studio adapter. Vortex fixtures provide an explicit radial-profile array because AgencityLab deliberately provides no fake exact profile. These tests cover generation, not defect detection.

Topology compares public `phase_winding` on the exact configured contour. Thermodynamic tests compare direct `total_dissipated_power`, `total_entropy_production` and `field_agencial_entropy` frame by frame. No Studio formula is used to generate expected values.

Blocking Plan 13 regressions include:

- wrong initial `phi_0` or `phi_dot_0`;
- axis-order or N-D shape corruption;
- non-uniform grid silently resampled instead of rejected;
- wrong boundary object/value mapping;
- wrong model parameter or numerical `dt_solver`/step mapping;
- silent identity between `beta_obs` and `phi` or automatic Research-run creation;
- complex dtype/value loss or float downcast;
- mutation of the immutable Research input, completed Run or result artifact;
- an unsupported Gravity/effective-beta/quantum/cosmology execution endpoint appearing in Plan 13;
- private `agencitylab.core` imports;
- Studio-side `np.gradient`, `np.diff`, `np.roll`, `solve_ivp`, FFT or equivalent hidden field numerics in the Research adapter;
- cross-Workspace Research data access;
- resource-limit truncation instead of clear rejection;
- a failed Lab configuration producing a completed artifact.

Tests also verify capability classification: autonomous dynamics, the explicit bridge, coherent initializers, topology and the selected thermodynamic subset are `SUPPORTED`; Gravity simulation is `UNAVAILABLE`; effective-beta, quantum and cosmology are `OUT_OF_SCOPE` for Plan 13.

## Real worker coverage

Canonical, diagnostic, sensitivity, observable-field and Research-field execution are real Celery workloads. Only stable record UUIDs are sent through Redis.

The Plan 12 Playwright path exercises a small immutable NPZ observable field through `QUEUED -> worker -> public compute_agencity_field -> immutable artifact -> COMPLETED` and then checks the EXPERIMENTAL field workspace.

The Plan 13 Playwright path exercises a small autonomous field through `QUEUED -> Redis -> worker -> public Research solver -> immutable Research result -> COMPLETED`, then checks the visible RESEARCH status, field workspace, exact point and reproducibility provenance. A single representative real-worker Research path is sufficient; every Research model need not be duplicated in browser E2E because direct backend equivalence carries the scientific burden.

Scientific validation/configuration errors are expected to become safe failed records rather than uncontrolled retries.

## Playwright

Playwright covers user workflows, not every numeric permutation. Backend tests carry the combinatorial burden for roles, dimensions, axis orders, boundary conditions and parameter modes. E2E tests intentionally avoid pixel-perfect chart assertions, arbitrary canvas clicks and fixed sleeps.

## Negative/flat/unexpected outcomes

A test must not force a positive scientific label, preferred scale, coherent structure or visually attractive Research trajectory merely because a fixture was chosen for demonstration.

Valid outcomes include diagnostic no-detection/unknown states, sensitivity curves that are flat or unexpected, observable fields whose local `beta_obs` or `b_obs` values do not support any coherence claim, and Research fields that are unstable, trivial or structure-free.

Tests must never change canonical equations/parameters or Research equations/model parameters merely to obtain an attractive classification, spectrum, map, domain wall or vortex.

## Threshold, grid and field-operation tests

Any diagnostic threshold appearing in production code must be traceable to explicit user configuration, a public Lab contract, numerical safety or a test fixture.

Sensitivity grid values are user/study configuration, not theory constants. Field upload/element/display limits and Research element/step/output limits are operational guards only. Tests must ensure Studio rejects oversized requests rather than silently truncating scientific data.

Plan 12 tests and code review additionally protect the absence of spatial CRM, spatial derivatives, automatic spatial averaging, interpolation, resampling, smoothing, normalization and signal-derived physical parameter maps. Plan 13 protects the absence of duplicated autonomous PDEs, topology equations, thermodynamic equations, gravity equations and browser-side defect detection.

## Security and isolation

Blocking regressions include cross-Workspace canonical/diagnostic/sensitivity/observable-field/Research result access, Viewer escalation, mismatched pinned hashes, public storage URLs, leaked backend paths and mutation of historical artifacts. NPY readers use `allow_pickle=False`; object dtype is not a supported scientific artifact format.

## CI acceptance

Plan 13 is not complete merely because focused tests pass. Required CI must remain healthy through PostgreSQL, frontend build, Playwright, Docker/Compose readiness and Redis/Celery execution. Report only counts and statuses actually observed from CI logs.

The key scientific CI rule is: Studio must reproduce the corresponding **AgencityLab public software contract** for identical inputs. These tests confirm software execution and reproducibility; they do not prove the underlying theory or experimentally validate autonomous Research-field physics.
