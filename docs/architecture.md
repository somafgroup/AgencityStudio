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
```

## Scientific boundary

AgencityLab is the scientific source of computation. Studio must not copy canonical formulas, import private/core implementation modules as shortcuts, or alter scientific parameters to make UI workflows convenient. The `labbridge` package is the only intended integration boundary. The current Studio runtime pins AgencityLab `1.1.3` and exposes an explicit compatibility contract.

## Web runtime

Django owns URLs, server-side rendering, security, persistence and future authorization. Uvicorn serves the ASGI application. PostgreSQL is the durable relational store. Static assets are built from Tailwind CSS and a small JavaScript bundle, then served with WhiteNoise in the current self-hosted foundation.

HTMX is reserved for useful server-rendered partial updates. Alpine.js owns local interface state only. Scientific or persisted domain state must not move into the browser merely for convenience.

## Background work

Celery is the asynchronous execution boundary and Redis is the broker/result backend in the current foundation. Long-running scientific jobs will later be submitted through this layer rather than blocking web requests. `common.health_ping` exists only as an infrastructure validation task; it is not a scientific workflow.

Task lifecycle vocabulary is defined by `common.tasks.TaskStatus`. Workflow-specific progress, cancellation semantics and result persistence belong to later domain plans and must be based on real worker state rather than fabricated progress.

## Operational health

`/health/` is a liveness endpoint and deliberately does not probe dependencies. `/health/ready/` verifies PostgreSQL connectivity, Redis broker connectivity and the installed AgencityLab compatibility contract. Neither endpoint exposes secrets.

## Deployment settings

`config.settings.development` is the default local configuration. `config.settings.production` requires an explicit production secret and allowed hosts, enables secure cookies and supports proxy/HTTPS/HSTS configuration through environment variables.
