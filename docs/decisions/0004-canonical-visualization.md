# ADR 0004 - Canonical scientific visualization

## Status

Accepted for Plan 8.

## Decision

Use **Apache ECharts 6.1.0** as AgencityStudio's primary interactive scientific chart engine.

The library is bundled locally with esbuild as a dedicated `scientific-workspace.js` bundle and is loaded only on canonical Results workspace pages. Django remains the backend and page-rendering framework; HTMX and Alpine.js remain available for ordinary progressive UI, while a scoped JavaScript controller owns chart synchronization for one `AnalysisRun`.

Only the ECharts modules required by Plan 8 are registered: line and scatter charts, grid, legend, tooltip, data zoom, visual map, mark line, ARIA support, and the Canvas renderer.

## Why ECharts

Plan 8 requires a coherent engine for:

- numerical line plots;
- complex-plane scatter/trajectory views;
- zoom and pan through `dataZoom`;
- linked coordinate views;
- legends and series visibility;
- large display series with bounded browser payloads;
- local PNG export;
- live Light/Dark/System re-theming;
- ARIA descriptions and decal support;
- self-hosting without a CDN or external chart service.

ECharts is Apache-2.0 licensed and provides these capabilities in one actively maintained open-source package. Its modular imports allow Studio to avoid shipping the complete optional chart ecosystem.

## Alternatives considered

### Plotly.js

Plotly provides strong scientific plotting and WebGL support, but its general-purpose bundle and interaction model are heavier than required for the first canonical workspace. Studio does not currently need a Plotly-specific figure schema or its broader scientific chart catalog.

### Chart.js

Chart.js is compact and approachable, but Plan 8 needs linked scientific interactions, complex-plane exploration, range navigation, and large-series controls that map more directly to ECharts' native model.

### D3

D3 is exceptionally flexible, but would require Studio to build and maintain substantially more chart behavior, accessibility, zoom, legends, and synchronization infrastructure itself. Plan 8 deliberately chooses a chart engine rather than a low-level visualization toolkit.

## Scientific constraints

ECharts is a **presentation engine only**. It never receives authority to calculate canonical Agencity quantities.

The browser consumes private visualization endpoints backed by the immutable Plan 7 result artifact. Stored `theta` is the only source for the canonical structural orientation chart. `U`, `beta`, and `b` are read from their stored complex NumPy arrays.

Elementary `real`, `imaginary`, `magnitude`, and complex phase values may be produced for display, but they are not persisted as new canonical results.

## Performance

Server-side display decimation bounds the number of points sent to a chart and preserves the original sample index on every returned display point. Zooming and selection never rewrite the canonical artifact. Exact sample inspection always uses the full-resolution sample endpoint.

## Accessibility

Charts include titles/descriptions and ECharts ARIA support. They supplement rather than replace the exact server-side canonical table and accessible sample navigator. Persistent sample selection is available by buttons, numeric input, and keyboard navigation; hover is not the only access path.

## Security

The library is self-hosted in Studio static assets. No CDN or chart SaaS is required. The visualization controller inserts server values using safe data structures and text nodes rather than unsafe HTML. Numerical endpoints are authenticated, Workspace-scoped, private/no-store responses and never expose storage paths.
