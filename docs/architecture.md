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
```

## Scientific boundary

AgencityLab is the scientific source of computation. Studio must not copy canonical formulas, import private/core implementation modules as shortcuts, or alter scientific parameters to make UI workflows convenient. The `labbridge` package is the only intended integration boundary. The current Studio runtime pins AgencityLab `1.1.3` and exposes an explicit compatibility contract.

## Identity and ownership boundary

`accounts.User` is the swappable Django user model and uses normalized email as the login identifier. It deliberately contains only identity and cross-session preferences; scientific metadata does not belong on the user record.

`workspaces.Workspace` is the logical ownership/security boundary for future Projects, Datasets, Systems, Analyses and Reports. Personal workspaces are private and have one personal owner. Organisation workspaces use explicit `WorkspaceMembership` rows. Roles are `OWNER`, `EDITOR`, `ANALYST` and `VIEWER`; instance `is_staff`/`is_superuser` flags are separate Django administration privileges and do not grant workspace membership.

All object-level workspace decisions are centralised in `workspaces.permissions`. Private workspace lookup is membership-scoped and intentionally returns 404 to a non-member, while a known member attempting an unauthorised management action receives 403. Hiding a button is never treated as authorisation.

Invitations are durable database records, while the bearer token exists only in the invitation URL/email. Studio stores a SHA-256 digest of a cryptographically random URL-safe token, enforces expiration/status/email binding and consumes accepted invitations transactionally with membership creation.

## Web runtime

Django owns URLs, server-side rendering, session authentication, CSRF protection, persistence and authorization. Uvicorn serves the ASGI application. PostgreSQL is the durable relational store. Static assets are built from Tailwind CSS and a small JavaScript bundle, then served with WhiteNoise in the current self-hosted foundation.

HTMX is reserved for useful server-rendered partial updates. Alpine.js owns local interface state only. Scientific or persisted domain state must not move into the browser merely for convenience.

Account theme, locale and timezone preferences are persisted on the user. Browser local storage mirrors the theme only to avoid visual flashing and to support signed-out pages; the authenticated account remains the durable source of truth.

## Background work

Celery is the asynchronous execution boundary and Redis is the broker/result backend in the current foundation. Long-running scientific jobs will later be submitted through this layer rather than blocking web requests. `common.health_ping` exists only as an infrastructure validation task; it is not a scientific workflow.

Account creation, membership changes and invitation acceptance remain synchronous transactional operations. Email delivery is synchronous in Plan 2, but invitation state is committed before delivery is attempted so an SMTP failure cannot corrupt workspace membership state.

## Operational health

`/health/` is a liveness endpoint and deliberately does not probe dependencies. `/health/ready/` verifies PostgreSQL connectivity, Redis broker connectivity and the installed AgencityLab compatibility contract. Identity adds no external readiness dependency beyond PostgreSQL.

## Deployment settings

`config.settings.development` is the default local configuration. `config.settings.production` requires an explicit production secret and allowed hosts, enables secure cookies and supports proxy/HTTPS/HSTS configuration through environment variables. Local authentication uses Django sessions rather than JWTs.

See `docs/accounts-and-workspaces.md` for the Plan 2 security and lifecycle contract.
