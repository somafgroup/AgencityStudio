# ADR 0002 — Background job execution

## Status

Accepted.

## Context

AgencityStudio will eventually run scientific analyses that can outlive a normal HTTP request. The web process therefore needs a durable asynchronous execution boundary with retries, explicit task state and a worker model that remains self-hostable.

## Options considered

- **Celery**: mature Python task queue, strong Django ecosystem, retries/routing/result backends and broad operational experience. It is heavier than simpler queues but fits long-running scientific work and future worker separation.
- **Dramatiq**: smaller API and good worker ergonomics, but a narrower ecosystem for workflow/result patterns expected by Studio.
- **RQ**: very simple Redis-backed jobs, attractive for small applications, but less suitable as the long-term orchestration contract once workflows, retries and multiple queues become important.

## Decision

Use Celery 5.x with Redis as the initial broker/result backend. Keep Celery behind application service/task boundaries so the scientific domain does not depend on queue-specific details.

Redis is infrastructure only; it does not hold canonical scientific state. PostgreSQL remains the durable application database, and scientific calculations remain in AgencityLab.

## Consequences

- Web requests can submit long-running work without blocking.
- Workers can be scaled independently from the Django web process.
- Docker Compose includes a dedicated worker service.
- CI validates a real broker → worker → result round trip with a deterministic non-scientific health task.
- Workflow-specific cancellation, progress and persistence semantics remain deferred until real domain jobs exist; they must not be simulated by arbitrary progress counters.
