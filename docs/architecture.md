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
        ↓
Project-owned Datasets
        ↓
Immutable DatasetVersions
```

## Scientific boundary

AgencityLab is the scientific source of computation. Studio must not copy canonical formulas, import private/core implementation modules as shortcuts, or alter scientific parameters to make UI workflows convenient. The `labbridge` package is the only intended integration boundary. The current Studio runtime pins AgencityLab `1.1.3` and exposes an explicit compatibility contract.

Projects are organisational containers only. Datasets describe source data and provenance only. Neither layer contains `A_ref`, `tau`, `w`, `P_c` or Agencity equations. Those belong to future System/Analysis layers.

Dataset inspection statistics are diagnostics, not physics. Observed sampling interval/frequency, ranges, missingness and quality findings must never silently define canonical physical parameters.

## Identity and ownership boundary

`accounts.User` is the swappable Django user model and uses normalized email as the login identifier. It deliberately contains only identity and cross-session preferences; scientific metadata does not belong on the user record.

`workspaces.Workspace` is the logical ownership/security boundary. Personal workspaces are private and have one personal owner. Organisation workspaces use explicit `WorkspaceMembership` rows. Roles are `OWNER`, `EDITOR`, `ANALYST` and `VIEWER`; instance `is_staff`/`is_superuser` flags are separate Django administration privileges and do not grant workspace membership.

`projects.Project` belongs to a Workspace, never directly to a user. Its UUID is the durable technical identity, its slug is readable and stable after creation, and `created_by` records provenance with `SET_NULL`. Project permissions inherit workspace membership. Studio does not introduce per-project ACLs.

`datasets.Dataset` belongs to a Project and represents a logical data identity. `datasets.DatasetVersion` is one immutable raw-source snapshot with a UUID, per-Dataset version number, generated private storage path, exact-source SHA-256 and importer provenance. `datasets.DatasetColumn` identifies columns by position plus preserved source name so duplicate headers cannot collapse into one logical column.

All object-level workspace, Project and Dataset decisions are centralised through existing permission policies. Private lookup is membership-scoped and intentionally returns 404 to a non-member, while a known member attempting an unauthorised management action receives 403. Hiding a button is never treated as authorisation.

Workspace deletion is refused while Projects exist. Project hard deletion is refused while Datasets exist. The foreign-key graph also uses protective deletion where appropriate, avoiding an implicit cascade that could destroy scientific sources.

Invitations are durable database records, while the bearer token exists only in the invitation URL/email. Studio stores a SHA-256 digest of a cryptographically random URL-safe token, enforces expiration/status/email binding and consumes accepted invitations transactionally with membership creation.

## Raw Dataset storage

Large scientific arrays do not live as one PostgreSQL row per sample. PostgreSQL stores ownership, metadata, provenance, column contracts, inspection summaries and references to artifacts. Raw source bytes live behind the private storage abstraction.

Local storage confines generated relative identifiers to `DATASET_STORAGE_ROOT`, writes DatasetVersion artifacts once, hashes the exact bytes while streaming them to storage and refuses overwrite. Browser-provided filenames are metadata only.

The local filesystem backend is the current concrete implementation, but Dataset services depend on a storage contract rather than a public-media URL. This keeps a future S3-compatible or institutional object-store backend possible without changing scientific models.

## Import and inspection

The import layer is split into lightweight importers for delimited text and XLSX. Importers expose source parsing/preview behavior without mixing it into Django views. Import configuration and importer schema version are persisted on DatasetVersion.

The HTTP path stores the original source and creates database metadata. Celery inspection is submitted only after transaction commit. The worker inspects the immutable artifact and writes derived metadata/findings; it never rewrites the raw source.

A monotonically increasing inspection generation protects reprocessing against stale task results. Import lifecycle and quality severity remain separate taxonomies.

Preview is server-side paginated. It may reread the raw source for the current Plan; any future acceleration artifact is an implementation cache, never a scientific replacement source.

## Web runtime

Django owns URLs, server-side rendering, session authentication, CSRF protection, persistence and authorization. Uvicorn serves the ASGI application. PostgreSQL is the durable relational store. Static assets are built from Tailwind CSS and a small JavaScript bundle, then served with WhiteNoise in the current self-hosted foundation.

HTMX is used for real server-rendered partial updates such as Dataset status and preview pagination. Alpine.js owns local interface state only. Scientific or persisted domain state must not move into the browser merely for convenience.

Account theme, locale and timezone preferences are persisted on the user. Browser local storage mirrors the theme only to avoid visual flashing and to support signed-out pages; the authenticated account remains the durable source of truth.

## Background work

Celery is the asynchronous execution boundary and Redis is the broker/result backend. Dataset ingestion inspection uses this boundary because parsing potentially non-trivial files must not block an HTTP request. `common.health_ping` remains the deterministic infrastructure validation task.

Account, membership and normal Project metadata operations remain synchronous transactional operations. Dataset source creation is transactional at the database level, while file/object storage is a separate atomicity domain handled explicitly by Dataset services.

## Operational health

`/health/` is a liveness endpoint and deliberately does not probe dependencies. `/health/ready/` verifies PostgreSQL connectivity, Redis broker connectivity and the installed AgencityLab compatibility contract. Dataset storage currently adds no remote readiness dependency.

## Deployment settings

`config.settings.development` is the default local configuration. `config.settings.production` requires an explicit production secret and allowed hosts, enables secure cookies and supports proxy/HTTPS/HSTS configuration through environment variables. Local authentication uses Django sessions rather than JWTs.

Dataset deployment settings include a private storage root and configurable upload/paste limits. They are operational safeguards, not scientific limits.

See `docs/accounts-and-workspaces.md` for identity/workspace security, `docs/projects.md` for the Project lifecycle contract and `docs/datasets.md` for Data Workspace provenance and inspection contracts.
