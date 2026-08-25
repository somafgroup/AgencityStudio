# Canonical Results Visualization

Plan 8 turns a completed canonical `AnalysisRun` into a read-only scientific exploration workspace. The source of truth is the immutable Plan 7 `AnalysisResultArtifact`; the visualization layer does not call `compute_agencity` and does not reconstruct canonical equations.

## Data path

```text
AnalysisRun COMPLETED
        |
AnalysisResultArtifact (ZIP_NPY_JSON schema 1)
        |
AnalysisResultReader
        |
Visualization service
        |
private Django endpoints
        |
ScientificWorkspaceController + Apache ECharts
```

The result reader is the single storage-aware read boundary. It validates the stored schema, Run identity, series inventory, shape, and dtype. It supports manifest, single-series, range, and exact-sample reads. The existing compatibility function that loads a full result also delegates to this reader.

## Stored canonical series

Schema 1 can persist the public Plan 7 inventory:

```text
xi
u
u_star
X_star
A_star
t_star
M
O
D
S
J
theta
U
beta
b
```

A historical artifact may contain fewer series. The UI only advertises series present in its manifest. Missing quantities are shown as unavailable; Studio never reconstructs them.

## Canonical workspace

The Results workspace provides stable deep links for:

- Overview
- Observable
- Dynamics
- Structure
- Contrast & Orientation
- Agencity State
- Agencity Flux
- Exact table
- Reproducibility

The Overview keeps the operational Run status separate from the `CANONICAL` scientific-status badge. `COMPLETED` means execution and immutable publication succeeded. It does not mean coherent, stable, or real agencity was detected.

## Complex values

`U`, `beta`, and `b` remain complex NumPy arrays in the canonical result artifact. The reader does not downcast them. JSON presentation encodes real and imaginary components explicitly and may additionally provide magnitude and phase for display.

`Re`, `Im`, magnitude, and `arg` are visualization representations when they are not independently stored canonical series. They are not inserted into the result artifact or into PostgreSQL as new scientific quantities.

The beta and b views include both coordinate-domain component views and a complex plane. The U complex plane is available in Contrast & Orientation when U exists in the artifact. Complex-plane colour follows the stored coordinate (or original sample index when no coordinate series exists); it is navigation context, not a scientific classification.

## Theta vs arg(beta)

**Structural orientation Theta is read from the AgencityLab result and is never reconstructed from beta.**

The canonical orientation chart reads the stored `theta` array. Studio never substitutes `np.angle(beta)` or a browser-computed beta phase for structural orientation. This distinction is protected by a regression test using a real Lab-backed result containing samples where stored Theta and `arg(beta)` differ.

Plan 8 does not unwrap Theta by default.

## Sample synchronization

One original sample index is the persistent selection for a workspace. Chart points retain their original sample index. Selection can come from a chart point, Previous/Next controls, direct sample input, or keyboard Left/Right navigation.

The selected-sample inspector then performs a separate exact full-resolution sample request. It never uses an approximate or decimated chart value. Complex-plane highlights and coordinate-chart cursors identify that same original sample. The selected index is also kept in a compact `?sample=` URL parameter while navigating result sections.

Playback is optional, user-triggered, and visits only stored sample indices. It never starts automatically and does not interpolate scientific samples. Global reduced-motion preferences disable chart animation.

## Display decimation

`VISUALIZATION_MAX_POINTS` is a UI/performance setting, not a scientific threshold. A long requested range may be represented by a bounded set of original indices for chart rendering. Both range endpoints are retained and every returned point includes its original index.

> Display decimation never alters the canonical result or the data used for scientific calculations.

Decimated values never feed Analysis execution, diagnostics, exports, or the exact selected-sample inspector. `result_sha256` naturally distinguishes caches or representations associated with different immutable results. Plan 8 does not persist a visualization cache because the current row limits and on-demand reader are sufficient.

## Exact table

The Exact table is server-paginated and keeps original result order. It never sorts samples by D, beta, b, or any other scientific value. Complex cells expose real and imaginary components without changing the stored dtype.

The table is also the principal accessibility fallback for users who cannot or do not wish to interpret a canvas chart.

## Endpoints

Plan 8 endpoints are internal UI endpoints, not a public `/api/v1/` contract:

```text
.../visualization/manifest/
.../visualization/series/
.../visualization/sample/
```

They require the same Workspace access as the Run. A non-member resolves through the normal object lookup as 404. Responses use `Cache-Control: private, no-store` and never include filesystem paths or storage-backend internals.

Complex/non-finite display JSON remains valid: exceptional NaN/Infinity components are emitted as `null` with a non-finite flag rather than invalid JSON numeric tokens. This changes only transport representation, never the artifact.

## Chart engine and bundling

Apache ECharts 6.1.0 is the single Plan 8 chart engine. It is imported modularly and built by esbuild into `static/js/scientific-workspace.js`. That bundle is referenced only by Results workspace pages, so ordinary pages such as login do not load the chart library.

Charts react to AgencityStudio's Light/Dark/System theme event and use the existing Design System variables. Legends and line styles accompany colour distinctions. Zoom/pan, Reset view, fullscreen, and current-view PNG export are display operations only.

## Accessibility

Each chart has a semantic title/description, series labels, ECharts ARIA support, and a link to the Exact table. Sample selection is persistent only through click/keyboard/controls; hover is a convenience rather than accessible state. The selected sample is reported through a restrained polite live region.

## No diagnostics in Plan 8

Plan 8 does **not** calculate or infer:

- coherence;
- angular variance or Theta stability;
- curvature;
- winding number;
- zeros;
- events or transitions;
- D peaks or S plateaus;
- signatures or regime classes;
- real agencity.

A visually striking trajectory is not automatically labelled coherent, chaotic, transitional, or a stable regime. Those belong to the separate diagnostic layer planned for Plan 9 and must use AgencityLab diagnostic contracts when available.

## Integrity rule

A completed Run is immutable. Visualization reads it; visualization never recalculates, normalizes, repairs, preprocesses, or modifies it. If the artifact is missing or corrupt, Studio reports an integrity problem rather than silently rerunning AgencityLab.
