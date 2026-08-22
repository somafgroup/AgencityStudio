# ADR 0003 — Local identity and workspace permission boundary

## Status

Accepted.

## Context

Plan 2 is the last low-cost point to choose the user identity model before Projects, Datasets and Analyses begin referencing users and workspaces. AgencityStudio must remain self-hostable, must not confuse instance administration with scientific collaboration roles, and must enforce private workspace access on the server.

## Options considered

- Django's default username-based `auth.User` plus separate profile records.
- A minimal custom Django user with email as the login identifier, while retaining Django session/password primitives.
- A larger external identity stack such as django-allauth immediately.

## Decision

Use a minimal custom `accounts.User` now, before domain data exists. Email is the unique login identifier. Continue using Django's maintained authentication, password reset/change, session rotation, CSRF and password-validation primitives rather than building a credential system or introducing JWTs.

Use application-level `Workspace`, `WorkspaceMembership` and central permission functions for logical tenancy. `is_staff`/`is_superuser` remain instance administration flags and never grant implicit workspace membership. Workspace privacy uses FK/membership isolation inside the shared PostgreSQL database; no schema-per-tenant or database-per-tenant architecture is introduced.

Authentication is implemented without an additional identity dependency because Plan 2's required local flows are covered by Django primitives. OAuth/OIDC and social providers remain optional future integrations rather than runtime requirements.

## Consequences

- Future domain objects can reference `settings.AUTH_USER_MODEL` and a Workspace from the beginning.
- Email-login and password recovery remain provider-independent.
- Changing the user model later is avoided once domain migrations exist.
- Permission logic stays reusable by future views/services/APIs.
- Email verification, federation and advanced anti-abuse controls remain explicit future hardening rather than partially implemented identity features.
