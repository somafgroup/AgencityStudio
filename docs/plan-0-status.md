# Plan 0 status

The technical foundation is complete for the current pre-domain stage of AgencityStudio.

Implemented foundations include Django/ASGI, PostgreSQL, Redis-backed Celery workers, Docker Compose, static/frontend builds, environment-based configuration, production settings, operational health/readiness endpoints, AgencityLab integration through `labbridge`, automated tests and CI validation.

The scientific runtime contract is pinned to AgencityLab `1.1.3`. Studio does not reimplement Agencity equations.

Plan 1 subsequently added the visible application shell, navigation, responsive design system, themes, accessibility foundations and browser smoke coverage.

Domain functionality such as accounts, real projects, datasets, scientific analyses, reports and exports belongs to later plans and is not a missing Plan 0 item.
