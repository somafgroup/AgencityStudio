# Architecture overview

AgencityStudio follows a strict dependency direction:

```text
Theory of Agencity
        ↓
AgencityLab scientific implementation
        ↓ public API only
AgencityStudio labbridge
        ↓
Django orchestration and presentation
        ↓
Users + Workspaces + explicit memberships
        ↓
Workspace-owned Projects
        ├──────────────────────────────┐
        ↓                              ↓
Project-owned Datasets          Project-owned Systems
        ↓                              ↓
Immutable DatasetVersions       stable System identity
        ↓                              ↓
explicit ordered preparation    immutable SystemRevisions
        ↓                              ↓
Immutable PreparedDataArtifacts observable + physical/contextual context
        └───────────────┬──────────────┘
                        ↓
              Project-owned Analysis
                        ↓
             immutable AnalysisRun
                        ↓
          labbridge → compute_agencity
                        ↓
       private immutable result artifact
```

## Scientific boundary

AgencityLab is the scientific source of computation. Studio must not copy canonical formulas, import private/core implementation modules as shortcuts, or alter scientific parameters to make UI workflows convenient. The `labbridge` package is the only intended integration boundary. The current Studio runtime pins AgencityLab `1.1.3` and exposes an explicit compatibility contract.

Projects are organisational containers only. Datasets describe source data and provenance. The Data Preparation layer may explicitly transform data. Systems document the studied physical/scientific context. Only the Analysis execution layer invokes the canonical AgencityLab public API.

Dataset inspection statistics are diagnostics, not physics. Observed sampling interval/frequency, ranges, missingness and quality findings must never silently define canonical physical parameters. Preparation `dt` is a sampling interval only and must not be confused with structural `tau` or CRM window `w`.

Plan 6 records `A_ref`, `tau`, `w` and `P_c` as explicit physical/contextual parameters of a SystemRevision. Studio does not infer them from standard deviation, MAD, signal range, extrema, dominant period, autocorrelation, sampling interval or signal power. `w` left unspecified is preserved as such; Studio does not store a fabricated `w=tau` value.

Plan 7 pins those exact inputs in an immutable AnalysisRun. An unspecified `w` is passed to `compute_agencity` as `None`. Studio may preflight structural source contracts, but it does not substitute `tau` for `w`; AgencityLab remains authoritative for the public omitted-window convention and exposes the effective `memory_window` in the returned result metadata.

`labbridge.scientific_context` may inspect the public `compute_agencity()` signature and mirror its public scalar input contracts. `labbridge.execution.execute_canonical_analysis` is the single execution adapter and calls only the package-root `agencitylab.compute_agencity`. No Studio module calculates `u_star`, `X_star`, `A_star`, `M`, `O`, `D`, `S`, `J`, `Theta`, `U`, `beta` or `b`.

## Identity and ownership boundary

`accounts.User` is the swappable Django user model and uses normalized email as the login identifier. It deliberately contains only identity and cross-session preferences; scientific metadata does not belong on the user record.

`workspaces.Workspace` is the logical ownership/security boundary. Personal workspaces are private and have one personal owner. Organisation workspaces use explicit `WorkspaceMembership` rows. Roles are `OWNER`, `EDITOR`, `ANALYST` and `VIEWER`; instance `is_staff`/`is_superuser` flags are separate Django administration privileges and do not grant workspace membership.

`projects.Project` belongs to a Workspace, never directly to a user. Its UUID is the durable technical identity, its slug is readable and stable after creation, and `created_by` records provenance with `SET_NULL`. Project permissions inherit workspace membership. Studio does not introduce per-project ACLs.

`datasets.Dataset` belongs to a Project and represents a logical data identity. `datasets.DatasetVersion` is one immutable raw-source snapshot with a UUID, per-Dataset version number, generated private storage path, exact-source SHA-256 and importer provenance. `datasets.DatasetColumn` identifies columns by position plus preserved source name so duplicate headers cannot collapse into one logical column.

`datasets.DataPreparation` pins one exact DatasetVersion and stores an ordered machine-readable recipe. `datasets.PreparedDataArtifact` is the immutable materialization produced by one preparation. Source SHA-256, recipe fingerprint and prepared SHA-256 are deliberately separate identities.

`systems.System` also belongs to a Project. It represents the durable identity of the studied physical/scientific system and is intentionally independent from any one Dataset. `created_by` records application provenance but does not define ownership.

`systems.SystemRevision` is an immutable snapshot of scientific context. A revision contains contextual metadata, one or more `ObservableDefinition` rows, parameter provenance for `A_ref`, `tau`, `w` and fixed scalar `P_c`, and lightweight `ScientificReference` rows. `System.current_revision` is an UX convenience only; historical analyses reference an exact SystemRevision.

`analyses.Analysis` is a mutable Project-owned user workspace for a named canonical configuration. `analyses.AnalysisRun` is the immutable reproducibility boundary for one execution. Each Run pins exactly one DatasetVersion or PreparedDataArtifact, source SHA-256 and lineage, stable coordinate/observable mapping, exact SystemRevision/ObservableDefinition, parameter and option snapshots, software versions and an execution fingerprint. Run numbers are unique per Analysis and allocated while the Analysis row is locked.

`analyses.AnalysisResultArtifact` is a private one-to-one immutable result object. PostgreSQL stores metadata and the manifest; canonical arrays are stored in a versioned ZIP containing JSON plus `.npy` arrays with `allow_pickle=False`. Complex dtypes are preserved. The source hash, execution fingerprint and result artifact SHA-256 remain distinct identities.

All object-level workspace, Project, Dataset, preparation, System and Analysis decisions are centralised through existing permission policies. Private lookup is membership-scoped and intentionally returns 404 to a non-member, while a known member attempting an unauthorised management action receives 403. Hiding a button is never treated as authorisation.

The Analyst role may create and run derived preparations, create/revise/duplicate Systems and create/configure/run Analyses, but still cannot mutate original Dataset metadata/source, administer the Workspace or perform Owner-only hard deletion. Viewer is read-only for Analysis and completed canonical results.

Workspace deletion is refused while Projects exist. Project hard deletion is refused while Datasets, Systems or Analyses exist. DatasetVersions, PreparedDataArtifacts and SystemRevisions referenced by AnalysisRuns are protected from deletion. The foreign-key graph avoids implicit cascades that could destroy reproducibility inputs.

Invitations are durable database records, while the bearer token exists only in the invitation URL/email. Studio stores a SHA-256 digest of a cryptographically random URL-safe token, enforces expiration/status/email binding and consumes accepted invitations transactionally with membership creation.

## Dataset versus System versus Analysis

The three concepts answer different questions:

```text
Dataset / PreparedDataArtifact
What measurements or prepared values do I have?

System / SystemRevision
What system is being studied, what does the observable mean,
and which physical/contextual parameters justify the calculation?

Analysis / AnalysisRun
Which exact source and exact SystemRevision are associated,
how are columns mapped, and what exact canonical computation was requested?
```

The Analysis layer does not mutate either side of that association. Creating a new DatasetVersion or SystemRevision after a completed Run never changes the historical Run.

## Units and scientific-context provenance

The shared Pint-backed unit helper is used by both explicit Data Preparation conversion and Analysis/System dimensional validation; Studio does not maintain a second unit engine. System revisions preserve the value and unit as entered. Known units are checked dimensionally, while unknown labels are preserved and marked as not automatically validated rather than guessed or treated as dimensionless.

Canonical Analysis execution uses the strict no-conversion policy. The selected source coordinate and observable must already use the exact unit representation expected by the selected System context. Dimensionally compatible but differently scaled labels such as `ms` versus `s`, or `km/h` versus `m/s`, are not converted during Analysis execution; such conversion must be an explicit PreparedData recipe.

The System configuration fingerprint and Analysis execution fingerprint are deterministic SHA-256 identifiers of different contracts. The result SHA-256 identifies exact stored result bytes. None of these fingerprints is evidence that a context or result is scientifically meaningful.

Project Activity and scientific provenance remain separate. Activity records that a user created, queued, completed or failed an Analysis Run. The AnalysisRun and result manifest record the reproducibility contract.

## Raw Dataset storage

Large scientific arrays do not live as one PostgreSQL row per sample. PostgreSQL stores ownership, metadata, provenance, column contracts, inspection summaries and references to artifacts. Raw source bytes, prepared materializations and canonical result artifacts live behind the private storage abstraction.

Local storage confines generated relative identifiers to `DATASET_STORAGE_ROOT`, writes artifacts once, hashes exact bytes while streaming them to storage and refuses public-media exposure. Analysis result publication uses a temporary file and atomic rename so a completed artifact is never partially visible.

The local filesystem backend is the current concrete implementation, but Dataset and Analysis services depend on a storage contract rather than a public-media URL. This keeps a future S3-compatible or institutional object-store backend possible without changing scientific models.

## Import and inspection

The import layer is split into lightweight importers for delimited text and XLSX. Importers expose source parsing/preview behavior without mixing it into Django views. Import configuration and importer schema version are persisted on DatasetVersion.

The HTTP path stores the original source and creates database metadata. Celery inspection is submitted only after transaction commit. The worker inspects the immutable artifact and writes derived metadata/findings; it never rewrites the raw source.

A monotonically increasing inspection generation protects reprocessing against stale task results. Import lifecycle and quality severity remain separate taxonomies.

Preview is server-side paginated. It may reread the raw source; any acceleration artifact is an implementation cache, never a scientific replacement source.

## Data preparation

Preparation is a separate Studio-owned layer upstream of AgencityLab. It uses a controlled transformation registry rather than user-provided code. No `eval`, `exec`, arbitrary Python expression, shell path or SQL fragment is accepted from the browser.

The currently implemented operations are explicit time/row crop, explicit row exclusion, missing-row removal, linear interpolation without extrapolation, uniform resampling with explicit `dt`, moving-average smoothing, compatible unit conversion through Pint, column selection and explicit stable time sorting. Frequency filtering is deliberately deferred until its sampling, cutoff/order, phase and anti-alias contracts are specified rather than hidden behind defaults.

The current engine materializes deterministic UTF-8 CSV. Execution is bounded by configurable `DATA_PREPARATION_MAX_ROWS` because the current transformation implementation uses an in-memory numerical table. This is an implementation safety limit, not a scientific law.

Each execution records source version/hash, ordered recipe, recipe fingerprint, Studio/Python/engine/dependency versions, timing/warnings and prepared artifact hash. READY artifacts are write-once. A changed recipe or re-run creates a new preparation record instead of rewriting an existing result.

Prepared output is inspected using the same data-quality contract as raw data, but raw findings remain unchanged. READY means materialization succeeded, not that a source is scientifically appropriate for a canonical Analysis.

## Canonical Analysis execution

Analysis execution reads exactly the selected coordinate and observable positions from the pinned source. It never sorts, interpolates, resamples, filters, fills, smooths, standardizes, normalizes or converts them. Non-finite, non-monotonic, irregular or unit-incompatible data are rejected with preparation guidance rather than modified.

A Run is inserted in `QUEUED` before Celery publication, and task publication occurs in `transaction.on_commit()`. Redis receives only the Run UUID. The worker locks the Run, changes it to `RUNNING`, reloads the immutable source/mapping/parameters, calls Lab, serializes the complete public result and only then marks the Run `COMPLETED`. Duplicate task delivery is guarded by the status transition and one-to-one result artifact.

Lab validation errors are deterministic failures and are not automatically retried. A queued Run may be cancelled; once the public AgencityLab call is running, Studio does not pretend it can cooperatively interrupt that synchronous computation.

`COMPLETED`, `FAILED` and `CANCELLED` are operational states only. Plan 7 does not calculate coherence, angular variance, curvature, winding, regimes or a “real agencity” verdict.

## Web runtime

Django owns URLs, server-side rendering, session authentication, CSRF protection, persistence and authorization. Uvicorn serves the ASGI application. PostgreSQL is the durable relational store. Static assets are built from Tailwind CSS and a small JavaScript bundle, then served with WhiteNoise in the current self-hosted foundation.

HTMX is used for real server-rendered partial updates such as Dataset/preparation/Analysis status and preview pagination. Alpine.js owns local interface state only. Scientific or persisted domain state must not move into the browser merely for convenience.

Account theme, locale and timezone preferences are persisted on the user. Browser local storage mirrors the theme only to avoid visual flashing and to support signed-out pages; the authenticated account remains the durable source of truth.

## Background work

Celery is the asynchronous execution boundary and Redis is the broker/result backend. Dataset ingestion inspection, prepared-data materialization and canonical Analysis execution use this boundary because non-trivial scientific files and computation must not block an HTTP request. `common.health_ping` remains the deterministic infrastructure validation task.

Database rows and file/object storage are separate atomicity domains; task publication occurs after transaction commit and result files are published atomically before the Run can become `COMPLETED`.

## Operational health

`/health/` is a liveness endpoint and deliberately does not probe dependencies. `/health/ready/` verifies PostgreSQL connectivity, Redis broker connectivity and the installed AgencityLab compatibility contract. It does not run a scientific Analysis as a health probe.

## Deployment settings

`config.settings.development` is the default local configuration. `config.settings.production` requires an explicit production secret and allowed hosts, enables secure cookies and supports proxy/HTTPS/HSTS configuration through environment variables. Local authentication uses Django sessions rather than JWTs.

Dataset deployment settings include a private storage root, configurable upload/paste limits, preparation row limit and Analysis row limit. These are operational safeguards, not scientific limits.

See `docs/accounts-and-workspaces.md` for identity/workspace security, `docs/projects.md` for the Project lifecycle contract, `docs/datasets.md` for raw Data Workspace provenance, `docs/data-preparation.md` for explicit transformations and prepared-data lineage, `docs/systems.md` for immutable scientific-context versioning, and `docs/analyses.md` for canonical Analysis execution and result storage.
