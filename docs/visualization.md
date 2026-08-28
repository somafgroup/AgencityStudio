# Scientific Results Visualization

AgencityStudio presents canonical, diagnostic, sensitivity and observable-field science as distinct layers over immutable artifacts.

Plan 8 visualizes a completed canonical `AnalysisRun`. Plan 9 visualizes a separate immutable `DiagnosticRun`. Plan 10 adds a scale/window workspace over an immutable `SensitivityStudy`. Plan 12 adds an **EXPERIMENTAL Observable Spatial Agencity Field** workspace over an immutable field result. None of these browser layers performs scientific computation.

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

## Sensitivity data path

```text
completed AnalysisRun
  ↓ backend-only public AgencityLab multiscale/window execution
SensitivityStudy COMPLETED
  ↓
SensitivityResultArtifact (ZIP_NPY_JSON)
  ↓
private sensitivity manifest/chart/table endpoints
  ↓
Sensitivity workspace controller + Apache ECharts 6.1.0
```

The scale axis is `tau` for `TAU_MULTISCALE` and `w` for `W_SENSITIVITY`. It is not the signal coordinate. Browser code does not call AgencityLab, detect peaks, select optima, normalize curves or update physical parameters.

## Observable spatial field data path — Plan 12

```text
EXPERIMENTAL field AnalysisRun COMPLETED
  ↓
AnalysisResultArtifact (ZIP_NPY_JSON, N-D arrays preserved)
  ↓
ObservableFieldResultReader
  ↓
private manifest / spatial slice / exact point / local trace endpoints
  ↓
Field workspace controller + Apache ECharts 6.1.0
```

The workspace reads the exact stored AgencityLab field result. It never reruns `compute_agencity_field` during display and never creates a second field equation in JavaScript or Django.

For one spatial dimension, the workspace supports time × space heatmaps for available quantities such as `u`, `|beta_obs|` and `|b_obs|`. For two spatial dimensions, it renders an exact selected-time spatial map. For more spatial dimensions, users explicitly choose displayed dimensions and fixed indices for the remaining dimensions. Studio does not automatically average, maximize, project or apply PCA over hidden dimensions.

The selected state is an exact time index plus exact spatial indices. Exact point inspection always reads the full-resolution artifact. Local temporal traces read one exact spatial trajectory from the N-D result. Large views may use display-only reduction, but scientific artifacts, exact point endpoints and trace values remain full resolution.

## Explicit scientific layers

UI badges and help text keep the distinction visible:

```text
CANONICAL RESULT
       ↓
DIAGNOSTIC INTERPRETATION

CANONICAL RUN
       ↓
SENSITIVITY STUDY

EXPERIMENTAL OBSERVABLE FIELD
u(x,t) -> beta_obs(x,t), b_obs(x,t)
```

Canonical quantities remain canonical. Diagnostic annotations and sensitivity comparisons never become canonical variables merely because they appear in the same Analysis workspace. Observable-field orchestration remains experimental and is never presented as autonomous field dynamics.

The UI must not imply that non-zero `beta`, non-zero local `beta_obs`, high `D`, large `b_obs`, a multiscale maximum, or a criterion-specific `w_opt` proves a physical conclusion beyond the corresponding Lab contract.

## Structural orientation

Canonical scalar structural orientation is stored `theta` returned by AgencityLab. The canonical orientation plot and all orientation-aware diagnostics use that contract.

`arg(beta)` or `arg(beta_obs)` is only a display phase of a complex value and may differ from structural `Theta`. It is never used as a fallback for missing canonical structural orientation. AgencityLab 1.1.3 `ObservableAgencityFieldResult` does not expose a public field `theta`; Plan 12 therefore does not invent one.

## Exact sample and field synchronization

Canonical and diagnostic workspaces use the original zero-based canonical sample index internally. Sensitivity studies use the persisted scale-candidate order.

Observable-field workspaces use the stored time index and N-D spatial index tuple. A selected point therefore corresponds to one exact stored cell. Tooltips or map rendering must not interpolate a value and present it as a measured or computed exact sample.

## Display-only decimation and representation

Large canonical/diagnostic series may be reduced to a subset of original indices for browser display. Decimation is never used by scientific execution, artifact generation or exact inspection.

Sensitivity grids are operationally bounded by `SENSITIVITY_MAX_POINTS`; Studio rejects oversized studies rather than silently truncating them. Field sources/results use field-specific operational limits and private slice/trace endpoints rather than pushing an entire large N-D array to the browser.

Stored complex `U`, `beta`, `b`, `beta_obs`/`b_obs` aliases and multiscale `b`/`beta` arrays preserve their NumPy complex dtype. Browser payloads may expose real, imaginary, magnitude and phase representations for display only. No display transform is persisted as a new scientific result.

## Diagnostic series and discrete outputs

When the Lab report supplies sample-indexed diagnostic series, Studio may plot them with the existing scientific bundle. Discrete events/transitions are rendered as tables using Lab-provided indices/coordinates. Empty tables or `undetermined` classifications are valid results and are displayed honestly.

Studio does not invent overlays by applying browser thresholds to canonical or field series.

## Tau multiscale presentation

The tau workspace plots a selected Lab-returned summary against the exact Lab-returned `tau` array and exposes the exact values in a table.

The table also displays the Lab-returned effective `w` per tau scale. A visual maximum is not marked or labeled as a physical `tau` or another automatic scientific conclusion.

## Window sensitivity presentation

The window workspace plots Lab-returned `phi2` or other returned descriptive values against exact candidate `w` values.

When Lab returns `w_opt`, Studio labels it **Lab-reported numerical window optimum** and displays the criterion and selection status. It does not rewrite the base Run or SystemRevision.

## Real-agencity presentation

The Real Agencity view reflects the exact Lab diagnostic report. If thresholds required by Lab are absent, the UI preserves `undetermined` rather than manufacturing a binary verdict. A non-zero beta alone is explicitly described as insufficient evidence.

Plan 12 adds no spatial real-agencity diagnostic, spatial coherence map, winding map, spatial zero detector or spatial regime classifier. A local non-zero `beta_obs` remains only a local observable-field value.

## ECharts bundle

Apache ECharts 6.1.0 remains the only charting library and is bundled locally.

- `frontend/scripts/scientific-workspace.js` serves canonical/diagnostic time/sample exploration;
- `frontend/scripts/sensitivity-workspace.js` serves scale/window results;
- `frontend/scripts/field-workspace.js` serves Plan 12 observable-field slicing and local traces.

No CDN fallback or second plotting framework is introduced.

## Accessibility

Important plotted quantities have textual/tabular alternatives. Exact canonical values are available through the sample inspector, diagnostic discrete results use ordinary tables, sensitivity results provide an exact scale table, and the field workspace exposes exact selected-point/local-trace information.

Charts use ECharts ARIA support and descriptive labels. Time and simple spatial-index navigation remain available through ordinary controls so inspection does not depend only on canvas hover or colour.

## Privacy and security

All scientific numerical endpoints:

- require authenticated Workspace-scoped object access;
- return 404 to non-members where object discovery must be hidden;
- use private/no-store response policy;
- never expose storage paths or filesystem roots.

Canonical, diagnostic, sensitivity and observable-field artifacts follow the same private-storage rule.

## Scientific boundary review

Production visualization code must not contain substitute implementations such as:

- `np.var(theta)` as official angular variance;
- `np.unwrap(np.angle(beta))` as official winding;
- custom curvature formulas;
- `find_peaks`-based Studio scientific detection;
- browser regime or real-agencity thresholds;
- `np.argmax`/peak selection that promotes a multiscale point to physical `tau`;
- a browser `w` optimizer or automatic update of System/Run parameters;
- spatial gradients, Laplacians or neighbour-correlation CRM;
- automatic spatial mean/max/PCA reductions presented as field science;
- reconstruction of field `Theta` from `arg(beta_obs)`.

Such scientific computations belong to AgencityLab or to explicit future scientific contracts. Studio renders public outputs and exact stored values.

See `docs/diagnostics.md`, `docs/sensitivity-and-multiscale.md` and `docs/observable-spatial-fields.md` for detailed contracts.
