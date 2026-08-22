# Contributing to AgencityStudio

AgencityStudio is the web interface and orchestration layer around AgencityLab. Contributions should keep the application usable for non-programmers without creating a second scientific implementation.

## Scientific boundary

Scientific computations must remain delegated to documented AgencityLab public APIs through `labbridge`. Do not copy canonical equations into Studio, import private AgencityLab internals as shortcuts, or infer physical parameters silently in UI code.

When Studio requires a scientific capability that AgencityLab does not expose publicly, the correct sequence is to improve AgencityLab first and then adopt the released public API explicitly.

## Development workflow

Create a focused branch from current `main`, keep the change as small as practical, add tests for meaningful behavior and open a pull request. Repository changes should pass the same validation used by CI.

Useful commands:

```bash
ruff check config common labbridge tests
pytest
npm run build
npm run test:e2e
```

Docker-shaped integration can be exercised with the Compose workflow documented in the README.

## UI changes

Reuse the existing design system and server-rendered architecture. HTMX is preferred for useful server partial updates; Alpine.js is for local UI state. Avoid introducing a SPA framework unless a future requirement demonstrates that the existing architecture cannot meet it cleanly.

Keep accessibility, responsive behavior, loading/error/empty states and Light/Dark/System themes working when a shared component changes.

## Pull requests

Explain the user-visible behavior, tests performed and any scientific-status implications. Do not describe CI as green unless the relevant checks actually ran successfully.
