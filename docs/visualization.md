# Scientific Results Visualization

AgencityStudio presents canonical, diagnostic and sensitivity science as distinct layers over immutable artifacts.

Plan 8 visualizes a completed canonical `AnalysisRun`. Plan 9 visualizes a separate immutable `DiagnosticRun`. Plan 10 adds a scale/window workspace over an immutable `SensitivityStudy`. None of these browser layers performs scientific computation.

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

## Explicit scientific layers

UI badges and help text keep the distinction visible:

```text
CANONICAL RESULT
       ↓
DIAGNOSTIC INTERPRETATION

CANONICAL RUN
       ↓
SENSITIVITY STUDY
```

Canonical quantities remain canonical. Diagnostic annotations and sensitivity comparisons never become canonical variables merely because they appear in the same Analysis workspace.

The UI must not imply that non-zero `beta`, high `D`, a multiscale maximum, or a criterion-specific `w_opt` proves a physical conclusion beyond the corresponding Lab contract.

## Structural orientation

Canonical structural orientation is stored `theta` returned by AgencityLab. The canonical orientation plot and all orientation-aware diagnostics use that contract.

`arg(beta)` is only a display phase of a complex value and may differ from structural `Theta`. It is never used as a fallback for a missing canonical `theta`.

## Exact sample synchronization

Canonical and diagnostic workspaces use the original zero-based canonical sample index internally. Human-facing controls render one-based sample numbers where appropriate, but endpoints and deep-link synchronization preserve the exact original index.

A diagnostic event or point therefore references the same canonical sample as the Results workspace. `sample=<index>` links let users move between those layers without an approximate chart-coordinate lookup.

Sensitivity studies use a different exact index: the persisted **scale-candidate order**. A selected scale is not a canonical time/sample selection and is not silently mapped to one.

## Display-only decimation and representation

Large canonical/diagnostic series may be reduced to a subset of original indices for browser display. Decimation is never used by scientific execution, artifact generation or exact inspection.

Sensitivity grids are operationally bounded by `SENSITIVITY_MAX_POINTS`; Studio rejects oversized studies rather than silently truncating them. The exact scale table uses every Lab-returned candidate.

Stored complex `U`, `beta`, `b` and multiscale `b`/`beta` arrays preserve their NumPy complex dtype. Browser payloads may expose real, imaginary, magnitude and phase representations for display only.

For a one-value-per-scale complex Lab summary such as `b_mean` or `beta_mean`, the sensitivity chart may explicitly show `|b_mean|` or `|beta_mean|` as a display representation. The source metric identity remains visible and the exact table/artifact retains real and imaginary values.

No display transform is persisted as a new scientific result.

## Diagnostic series and discrete outputs

When the Lab report supplies sample-indexed diagnostic series, Studio may plot them with the existing scientific bundle. Plan 9 includes presentation support for outputs such as `Sigma_Theta`, curvature and configured local real-agencity criteria when present.

Discrete events/transitions are rendered as tables using Lab-provided indices/coordinates. Empty tables or `undetermined` classifications are valid results and are displayed honestly.

Studio does not invent overlays by applying browser thresholds to canonical series.

## Tau multiscale presentation

The tau workspace plots a selected Lab-returned summary against the exact Lab-returned `tau` array and exposes the exact values in a table.

The table also displays the Lab-returned effective `w` per tau scale. This is especially important when the base Run requested `w` as unspecified: Studio preserves that request state and displays Lab's documented effective-window behavior rather than fabricating it before execution.

A visual maximum is not marked or labeled as `physical tau`, `true tau`, `best tau` or another automatic scientific conclusion.

## Window sensitivity presentation

The window workspace plots Lab-returned `phi2` or other returned descriptive values against exact candidate `w` values.

When Lab returns `w_opt`, Studio labels it **Lab-reported numerical window optimum** and displays the `Phi2` criterion and selection status. It does not rewrite the base Run or SystemRevision and does not relabel the optimum as physical memory.

Candidates rejected by structural preflight do not enter a queued study. Eligibility returned by Lab for valid candidates is displayed rather than hidden.

## Real-agencity presentation

The Real Agencity view reflects the exact Lab report. If thresholds required by Lab are absent, the UI preserves `undetermined` rather than manufacturing a binary verdict. A non-zero beta alone is explicitly described as insufficient evidence.

Sensitivity studies do not automatically rerun or modify real-agencity diagnostics.

## ECharts bundle

Apache ECharts 6.1.0 remains the only charting library and is bundled locally.

- `frontend/scripts/scientific-workspace.js` serves canonical/diagnostic time/sample exploration;
- `frontend/scripts/sensitivity-workspace.js` is scoped to one sensitivity result and scale axis.

Neither bundle is loaded as a scientific dependency on unrelated pages. No CDN fallback or second plotting framework is introduced.

## Accessibility

Important plotted quantities have textual/tabular alternatives. Exact canonical values are available through the sample inspector, diagnostic discrete results use ordinary tables, and sensitivity results provide an exact scale table.

Charts use ECharts ARIA support and descriptive labels. Sensitivity metrics are selectable with ordinary form controls; interpreting a result never depends only on canvas hover or colour.

## Privacy and security

All scientific numerical endpoints:

- require authenticated Workspace-scoped object access;
- return 404 to non-members where object discovery must be hidden;
- use private/no-store response policy;
- never expose storage paths or filesystem roots.

Canonical, diagnostic and sensitivity artifacts follow the same private-storage rule.

## Scientific boundary review

Production visualization code must not contain substitute implementations such as:

- `np.var(theta)` as official angular variance;
- `np.unwrap(np.angle(beta))` as official winding;
- custom curvature formulas;
- `find_peaks`-based Studio scientific detection;
- browser regime rules;
- browser real-agencity thresholds;
- `np.argmax`/peak selection that promotes a multiscale point to physical `tau`;
- a browser `w` optimizer or automatic update of System/Run parameters.

Such scientific computations belong to AgencityLab or to explicit future scientific contracts. Studio renders their public outputs.

See `docs/diagnostics.md` for Plan 9 and `docs/sensitivity-and-multiscale.md` for Plan 10.
