# ADR 0001 - Initial stack

## Decision

Use Django as backend framework with ASGI support, PostgreSQL as primary database, server-rendered HTML with HTMX and Alpine.js for progressive interaction.

## Rationale

The application requires scientific workflows, reproducibility and maintainability. A full SPA is not required at this stage.

AgencityStudio consumes AgencityLab through labbridge and does not duplicate scientific computation.
