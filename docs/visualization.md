# Scientific Results Visualization

AgencityStudio presents canonical and diagnostic science as two distinct layers over immutable artifacts.

Plan 8 visualizes a completed canonical `AnalysisRun`. Plan 9 adds visualization of a separate immutable `DiagnosticRun`. Neither layer performs scientific computation in the browser.

## Canonical data path

```text
AnalysisRun COMPLETED
  ↓
AnalysisResultArtifact (ZIP_NPY_JSON)
  ↓
AnalysisResultReader
  ↓
private visualization endpoints
  ↓
ScientificWorkspaceController + Apache ECharts 6.1.0
```

The canonical workspace reads stored values only. It never calls `compute_agencity` during display and never reconstructs canonical equations.

## Diagnostic data path

```text
AnalysisRun canonical result
  ↓ backend-only public AgencityLab diagnostic execution
DiagnosticRun COMPLETED
  ↓
DiagnosticResultArtifact
  ↓
private diagnostic manifest/series/sample endpoints
  ↓
ScientificWorkspaceController + Apache ECharts 6.1.0
```

The diagnostic browser path never computes coherence, angular variance, curvature, winding, events, regimes or real-agencity criteria. Those values already come from the backend public AgencityLab diagnostic API.

## Explicit scientific layers

UI badges and help text keep the distinction visible:

```text
CANONICAL RESULT
       ↓
DIAGNOSTIC INTERPRETATION
```

Canonical quantities remain canonical. Diagnostic annotations, classifications and evidence never become canonical variables merely because they appear on the same screen.

The UI must not imply that non-zero `beta` or high `D` proves real agencity.

## Structural orientation

Canonical structural orientation is stored `theta` returned by AgencityLab. The canonical orientation plot and all orientation-aware diagnostics use that contract.

`arg(beta)` is only a display phase of a complex value and may differ from structural `Theta`. It is never used as a fallback for a missing canonical `theta`.

## Exact sample synchronization

Both workspaces use the original zero-based canonical sample index internally. Human-facing controls render one-based sample numbers where appropriate, but endpoints and deep-link synchronization preserve the exact original index.

A diagnostic event or point therefore references the same canonical sample as the Results workspace. `sample=<index>` links let users move between layers without an approximate chart-coordinate lookup.

## Display-only decimation

Large series may be reduced to a subset of original indices for browser display. This rule applies to canonical and diagnostic series.

Decimation is never used by:

- `compute_agencity`;
- `analyze_agencity`;
- artifact generation;
- diagnostic event detection;
- regime classification;
- exact selected-sample inspection.

Every displayed point retains its original sample index. Selecting a point fetches the exact full-resolution stored values for that index.

## Canonical complex values

Stored complex `U`, `beta` and `b` preserve their NumPy complex dtype. Browser payloads may expose real, imaginary, magnitude and phase representations for display only.

Complex-plane trajectories are presentation views over stored canonical values, not new persisted scientific quantities.

## Diagnostic series and discrete outputs

When the Lab report supplies sample-indexed diagnostic series, Studio may plot them with the existing scientific bundle. Plan 9 includes presentation support for outputs such as `Sigma_Theta`, curvature and a configured local real-agencity criterion when actually present.

Discrete events/transitions are rendered as tables using Lab-provided indices/coordinates. Structural plateau and regime outputs remain diagnostic report content. Empty tables or `undetermined` classifications are valid results and are displayed honestly.

Studio does not invent overlays by applying browser thresholds to canonical series.

## Real-agencity presentation

The Real Agencity view reflects the exact Lab report. It may show status, evaluated fraction, configured thresholds and a local criterion when supplied.

If thresholds required by Lab are absent, the UI preserves `undetermined` rather than manufacturing a binary verdict. A non-zero beta alone is explicitly described as insufficient evidence.

Color is not the sole carrier of a scientific verdict. Textual status, configuration and provenance remain visible.

## ECharts bundle

Apache ECharts 6.1.0 remains the only charting library. It is locally bundled by `frontend/scripts/scientific-workspace.js` and loaded only on scientific workspace pages.

The diagnostic workspace uses the same stylesheet and controller as the canonical workspace. The controller is data-source agnostic: it reads the manifest/series/sample endpoints declared by the page and performs only display operations.

No CDN fallback or second plotting framework is introduced.

## Accessibility

Important plotted quantities have textual/tabular alternatives. Exact sample values are available through the shared sample inspector, and discrete diagnostics use ordinary tables.

Charts use ECharts ARIA support and descriptive labels. Keyboard-accessible sample controls do not depend on clicking canvas coordinates. Playback never starts automatically and reduced-motion preferences are respected.

## Privacy and security

All scientific numerical endpoints:

- require authenticated Workspace-scoped object access;
- return 404 to non-members where object discovery must be hidden;
- use private/no-store response policy;
- never expose storage paths or filesystem roots.

Diagnostic artifact access follows the same rules as canonical result access.

## Scientific boundary review

Production visualization code must not contain substitute implementations such as:

- `np.var(theta)` as official angular variance;
- `np.unwrap(np.angle(beta))` as official winding;
- custom curvature formulas;
- `find_peaks`-based Studio scientific detection;
- browser regime rules;
- browser real-agencity thresholds.

Such diagnostics belong to AgencityLab. Studio renders their public outputs.

See `docs/diagnostics.md` for the exact Plan 9 public diagnostic inventory and provenance contract.