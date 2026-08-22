# Accounts and workspaces

Plan 2 establishes the identity and permission boundary that later scientific domain objects must reuse.

## User model

AgencityStudio uses `accounts.User`, a minimal Django custom user model introduced before Projects/Datasets/Analyses reference identities. Email is the unique login identifier; Studio normalises it to lower case and PostgreSQL also enforces case-insensitive uniqueness. The profile contains only display name plus durable locale, timezone and theme preferences.

`is_staff` and `is_superuser` are Django instance-administration flags. They are deliberately unrelated to scientific/workspace roles.

A user created through the supported account manager receives one personal workspace and an Owner membership in the same transaction. Personal workspaces cannot be shared, left or deleted through normal workspace flows.

## Authentication

Plan 2 deliberately uses Django's maintained session authentication primitives rather than a JWT or a custom credential system. Available local flows are:

- signup;
- email/password sign in;
- POST sign out;
- password change;
- password reset through Django's single-use reset token mechanism.

Standard Django password validators, CSRF, session rotation on login and production secure cookies remain active.

`AGENCITYSTUDIO_SIGNUP_MODE` supports three deployment policies:

- `public`: public signup and invited signup are enabled;
- `invitation_only`: public signup is disabled; a valid invitation may create a new local account;
- `disabled`: self-service account creation is disabled, including invited signup. Existing accounts may still authenticate and accept invitations addressed to them.

## Workspaces and roles

A workspace is either `PERSONAL` or `ORGANISATION`. Collaboration is represented by explicit `WorkspaceMembership` records rather than a hidden many-to-many relationship.

Role semantics at the workspace level are intentionally small:

| Role | Plan 2 capability |
| --- | --- |
| `OWNER` | View/edit workspace, manage members/invitations/roles and delete an organisation workspace. |
| `EDITOR` | View/edit workspace content when later content models exist; cannot manage membership/security. |
| `ANALYST` | View workspace and is the future policy role for running analyses/creating analytical outputs. |
| `VIEWER` | Read-only workspace access. |

Plan 2 does not pretend to enforce Project/Dataset/Analysis permissions before those objects exist. Later plans should compose their policies from this membership foundation rather than silently broadening roles.

Organisation workspaces must keep at least one Owner. The last Owner cannot demote themselves, be removed or leave until another Owner exists. Database uniqueness prevents duplicate memberships.

## URL and permission policy

Workspace slugs are readable routing identifiers, never secrets. Every workspace lookup is constrained by the authenticated user's explicit membership.

- Anonymous users are redirected to login for authenticated workspace routes.
- A non-member requesting a private workspace slug receives 404, avoiding workspace enumeration.
- A member requesting a management action outside their role receives 403.
- Django staff/superuser status does not bypass application membership policies.

The reusable policy functions live in `workspaces.permissions`; multi-step state changes live in `workspaces.services` and use database transactions where atomicity matters.

## Invitations

`WorkspaceInvitation` stores the workspace, target email, requested role, inviter, status and timestamps. It never stores the raw bearer token. A cryptographically random URL-safe token is generated once and Studio stores only its SHA-256 digest.

Invitation states are `PENDING`, `ACCEPTED`, `REVOKED` and `EXPIRED`. Acceptance requires:

1. a valid pending token;
2. an unexpired invitation;
3. an authenticated email exactly matching the invited email;
4. atomic creation/reuse of the unique membership and marking the invitation accepted.

The raw token is not written by Studio application logging. Development email defaults to file output under `.emails/` rather than console output. Production email defaults to Django SMTP and is not tied to a SaaS provider.

Invitation creation is committed independently of email delivery. If SMTP delivery fails, the invitation remains valid and the user receives a non-sensitive warning instead of a traceback.

## Preferences

Theme, locale and timezone are account-persisted. The browser stores a mirrored theme value so the page can select a theme before the JavaScript bundle renders; authenticated account state remains authoritative and theme changes are POSTed with CSRF protection.

## Account deletion and email verification

These are intentionally not presented as complete in Plan 2.

Email verification is prepared by having a stable email identity, provider-independent email infrastructure and invitation email binding, but public signup verification/resend state is deferred. Adding it should reuse a maintained Django-compatible mechanism and must define throttling before being exposed broadly.

Full account deletion is deferred until Projects/Datasets/Reports have explicit ownership/retention semantics. Naively cascading an identity today would make future scientific retention behavior ambiguous. Any future deletion flow must first transfer or delete organisation ownership safely and define what happens to durable scientific provenance.

## Rate limiting and audit

No maintained rate-limiting or audit subsystem existed before Plan 2, so this plan does not add a large dependency solely for nominal completeness. Deployment hardening should add rate controls for login, password reset, verification resend and invitation sending before hostile public exposure.

The future audit layer should record categories such as login, logout, workspace creation, invitation/member/role changes without passwords, session keys, reset tokens or invitation tokens. Plan 2 does not introduce an unused audit framework.
