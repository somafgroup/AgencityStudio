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
                 future Analysis
```

## Scientific boundary

AgencityLab is the scientific source of computation. Studio must not copy canonical formulas, import private/core implementation modules as shortcuts, or alter scientific parameters to make UI workflows convenient. The `labbridge` package is the only intended integration boundary. The current Studio runtime pins AgencityLab `1.1.3` and exposes an explicit compatibility contract.

Projects are organisational containers only. Datasets describe source data and provenance. The Data Preparation layer may explicitly transform data. Systems document the studied physical/scientific context. None of these layers executes the Agencity pipeline.

Dataset inspection statistics are diagnostics, not physics. Observed sampling interval/frequency, ranges, missingness and quality findings must never silently define canonical physical parameters. Preparation `dt` is a sampling interval only and must not be confused with structural `tau` or CRM window `w`.

Plan 6 records `A_ref`, `tau`, `w` and `P_c` as explicit physical/contextual parameters of a SystemRevision. Studio does not infer them from standard deviation, MAD, signal range, extrema, dominant period, autocorrelation, sampling interval or signal power. `w` left unspecified is preserved as such; Studio does not store a fabricated `w=tau` value. A future Analysis may record AgencityLab's documented resolution when the public API is actually executed.

`labbridge.scientific_context` may inspect the public `compute_agencity()` signature and mirror its public scalar input contracts. It does not call the computation. AgencityLab 1.1.3 accepts finite strictly positive explicit `A_ref`, `tau` and `w`, and finite non-negative scalar `P_c`, including `P_c=0`.

## Identity and ownership boundary

`accounts.User` is the swappable Django user model and uses normalized email as the login identifier. It deliberately contains only identity and cross-session preferences; scientific metadata does not belong on the user record.

`workspaces.Workspace` is the logical ownership/security boundary. Personal workspaces are private and have one personal owner. Organisation workspaces use explicit `WorkspaceMembership` rows. Roles are `OWNER`, `EDITOR`, `ANALYST` and `VIEWER`; instance `is_staff`/`is_superuser` flags are separate Django administration privileges and do not grant workspace membership.

`projects.Project` belongs to a Workspace, never directly to a user. Its UUID is the durable technical identity, its slug is readable and stable after creation, and `created_by` records provenance with `SET_NULL`. Project permissions inherit workspace membership. Studio does not introduce per-project ACLs.

`datasets.Dataset` belongs to a Project and represents a logical data identity. `datasets.DatasetVersion` is one immutable raw-source snapshot with a UUID, per-Dataset version number, generated private storage path, exact-source SHA-256 and importer provenance. `datasets.DatasetColumn` identifies columns by position plus preserved source name so duplicate headers cannot collapse into one logical column.

`datasets.DataPreparation` pins one exact DatasetVersion and stores an ordered machine-readable recipe. `datasets.PreparedDataArtifact` is the immutable materialization produced by one preparation. Source SHA-256, recipe fingerprint and prepared SHA-256 are deliberately separate identities.

`systems.System` also belongs to a Project. It represents the durable identity of the studied physical/scientific system and is intentionally independent from any one Dataset. `created_by` records application provenance but does not define ownership.

`systems.SystemRevision` is an immutable snapshot of scientific context. A revision contains contextual metadata, one or more `ObservableDefinition` rows, parameter provenance for `A_ref`, `tau`, `w` and fixed scalar `P_c`, and lightweight `ScientificReference` rows. `System.current_revision` is an UX convenience only; future historical analyses must reference an exact SystemRevision.

Changing scientific context creates a new revision. Renaming the stable System identity does not. Revision numbers are unique per System and allocated while holding a row lock on the System, with a database uniqueness constraint as the final guard.

All object-level workspace, Project, Dataset, preparation and System decisions are centralised through existing permission policies. Private lookup is membership-scoped and intentionally returns 404 to a non-member, while a known member attempting an unauthorised management action receives 403. Hiding a button is never treated as authorisation.

The Analyst role may create and run derived preparations and may create/revise/duplicate Systems, but still cannot mutate original Dataset metadata/source, administer the Workspace or hard-delete a System. This allows scientific work while preserving raw acquisition and context history.

Workspace deletion is refused while Projects exist. Project hard deletion is refused while Datasets or Systems exist. DatasetVersions referenced by preparation lineage are protected from deletion. The foreign-key graph avoids implicit cascades that could destroy scientific sources or context provenance.

Invitations are durable database records, while the bearer token exists only in the invitation URL/email. Studio stores a SHA-256 digest of a cryptographically random URL-safe token, enforces expiration/status/email binding and consumes accepted invitations transactionally with membership creation.

## Dataset versus System versus Analysis

The three concepts answer different questions:

```text
Dataset / PreparedDataArtifact
What measurements or prepared values do I have?

System / SystemRevision
What system is being studied, what does the observable mean,
and which physical/contextual parameters justify the future calculation?

future Analysis
Which exact data source and exact SystemRevision are associated,
how are columns mapped to observables, and what is executed by AgencityLab?
```

Plan 6 deliberately persists no Dataset-column-to-System-observable mapping. A System can therefore be reused with multiple acquisitions or prepared artifacts without coupling its scientific identity to a single file. The future Analysis layer will make the association explicitly.

## Units and scientific-context provenance

The shared Pint-backed unit helper is used by both explicit Data Preparation conversion and System dimensional validation; Studio does not maintain a second unit engine. System revisions preserve the value and unit as entered. Known units are checked dimensionally, while unknown labels are preserved and marked as not automatically validated rather than guessed or treated as dimensionless.

The configuration fingerprint is a deterministic SHA-256 over canonical serialized scientific context. It includes relevant observables, units, parameters and metadata, but not timestamps or UI state. It establishes computational configuration identity only; it is not evidence that a context is scientifically correct.

Project Activity and scientific provenance remain separate. Activity records that a user created or revised a System. The SystemRevision records what `tau`, for example, was, its unit, origin and justification.

## Raw Dataset storage

Large scientific arrays do not live as one PostgreSQL row per sample. PostgreSQL stores ownership, metadata, provenance, column contracts, inspection summaries and references to artifacts. Raw source bytes and prepared materializations live behind the private storage abstraction.

Local storage confines generated relative identifiers to `DATASET_STORAGE_ROOT`, writes artifacts once, hashes exact bytes while streaming them to storage and refuses overwrite. Browser-provided filenames are metadata only.

The local filesystem backend is the current concrete implementation, but Dataset services depend on a storage contract rather than a public-media URL. This keeps a future S3-compatible or institutional object-store backend possible without changing scientific models.

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

Prepared output is inspected using the same data-quality contract as raw data, but raw findings remain unchanged. A successful preparation is not labelled “ready for Agencity”; the future Analysis layer must still select an exact SystemRevision and explicit observable mapping.

## Web runtime

Django owns URLs, server-side rendering, session authentication, CSRF protection, persistence and authorization. Uvicorn serves the ASGI application. PostgreSQL is the durable relational store. Static assets are built from Tailwind CSS and a small JavaScript bundle, then served with WhiteNoise in the current self-hosted foundation.

HTMX is used for real server-rendered partial updates such as Dataset/preparation status and preview pagination. Alpine.js owns local interface state only. Scientific or persisted domain state must not move into the browser merely for convenience.

Account theme, locale and timezone preferences are persisted on the user. Browser local storage mirrors the theme only to avoid visual flashing and to support signed-out pages; the authenticated account remains the durable source of truth.

## Background work

Celery is the asynchronous execution boundary and Redis is the broker/result backend. Dataset ingestion inspection and prepared-data materialization use this boundary because parsing/transformation of non-trivial files must not block an HTTP request. `common.health_ping` remains the deterministic infrastructure validation task.

Account, membership, Project, System identity and SystemRevision operations remain synchronous transactional operations. Database rows and file/object storage are separate atomicity domains; task publication occurs after transaction commit and result files are published only after successful materialization.

## Operational health

`/health/` is a liveness endpoint and deliberately does not probe dependencies. `/health/ready/` verifies PostgreSQL connectivity, Redis broker connectivity and the installed AgencityLab compatibility contract. Systems add no infrastructure dependency and do not alter readiness semantics.

## Deployment settings

`config.settings.development` is the default local configuration. `config.settings.production` requires an explicit production secret and allowed hosts, enables secure cookies and supports proxy/HTTPS/HSTS configuration through environment variables. Local authentication uses Django sessions rather than JWTs.

Dataset deployment settings include a private storage root, configurable upload/paste limits and a preparation row limit. They are operational safeguards, not scientific limits.

See `docs/accounts-and-workspaces.md` for identity/workspace security, `docs/projects.md` for the Project lifecycle contract, `docs/datasets.md` for raw Data Workspace provenance, `docs/data-preparation.md` for explicit transformations and prepared-data lineage, and `docs/systems.md` for immutable scientific-context versioning.
