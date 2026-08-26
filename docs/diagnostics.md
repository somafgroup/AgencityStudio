# Scientific Diagnostics

AgencityStudio 0.9 introduces a diagnostic layer that is deliberately separate from the canonical AnalysisRun.

```text
AnalysisRun COMPLETED
        |
        v
immutable canonical ZIP_NPY_JSON result
        |
        v
DiagnosticRun
        |
        v
public AgencityLab 1.1.3 diagnostic API
        |
        v
private immutable ZIP_JSON diagnostic artifact
```

## Scientific boundary

Canonical quantities remain exactly those computed by AgencityLab. Diagnostics consume them but do not redefine them.

Studio does not implement formulas for coherence, angular variance, curvature, winding, zero detection, event detection, regime classification, or real-agencity assessment. The diagnostic Lab boundary imports only public AgencityLab objects and functions.

A non-zero `beta` is not by itself a real-agencity diagnostic. High `D` is not by itself evidence of real agencity. Noise and chaotic signals may produce locally non-zero `beta`.

Diagnostic thresholds are configuration or Lab-defined diagnostic contracts, not canonical universal constants. An empty or negative diagnostic result is valid and is never converted into a positive result by modifying a threshold or canonical parameter.

## Public AgencityLab 1.1.3 contract

Plan 9 uses the public standard bundle:

```python
from agencitylab import AgencityResult, analyze_agencity
```

The canonical result artifact contains every public array needed by the public `AgencityResult` container. Studio rehydrates that public container from the immutable stored values. The stored canonical `theta` is mandatory and is passed explicitly.

Studio never substitutes `arg(beta)` for structural orientation. If an historical artifact does not contain canonical `theta`, Plan 9 diagnostics are unavailable for that artifact rather than reconstructed in Studio.

The public `analyze_agencity()` report used by Plan 9 has analysis schema `0.5` and provides the following theory-facing or diagnostic outputs.

### Coherence and orientation

The standard report includes structural-orientation angular variance `Sigma_Theta` and coherence summaries using canonical `Theta`. No Studio threshold is needed to compute the angular-variance diagnostic itself.

### Real-agencity evidence

The public Lab criterion separates:

- structural support `S`;
- low angular variance of structural orientation;
- significant `|b|`.

AgencityLab does not define universal numerical values for "low" angular variance or "significant" flux. Studio therefore leaves these thresholds blank by default. Without the contextual angular-variance and flux thresholds, the public report remains `undetermined` and Studio preserves that result.

If a user explicitly configures supported thresholds, the values are stored unchanged in the DiagnosticRun configuration and appear in the result provenance. A global boolean assessment is only requested when an explicit minimum evaluated fraction is also configured.

### Geometry and topology

The standard report includes beta-trajectory geometry and signed curvature where numerically defined. Geometry is defined on intrinsic `beta`, not on `b`.

The report also exposes net structural-orientation turns. The standard finite AnalysisRun interval is not silently declared to be a closed contour, so Studio does not force an integer winding number. The public winding diagnostic can therefore remain undefined while net turns remain available.

### Exact zeros and critical surface

The standard report exposes the exact Lab zero condition with its public default numerical tolerance (`atol=0`) and the `D = S` critical-surface crossing diagnostic. Studio does not replace either condition with an arbitrary near-zero threshold.

### Theta jumps

Theta-jump detection is only configured when the user explicitly provides the public angular threshold. Blank means not configured.

### Dynamic-intensity peaks

Plan 9 uses the standard unfiltered NumPy-only public `D`-peak detector. AgencityLab 1.1.3 can optionally apply prominence/distance filtering through its SciPy scientific extra, but Studio does not add SciPy merely to create a diagnostic preference in Plan 9.

### Structural plateaus

Structural-plateau detection requires an explicit slope threshold and minimum duration. Studio provides neither by default and requires the pair together when configured.

### Regime signature and classification

`regime_signature` is a threshold-free diagnostic summary. It is stored and shown separately from classification.

For non-null records, the public classifier remains `undetermined` when no contextual `RegimeCriteria` are supplied. Studio does not provide hidden criteria. Enabling non-null classification requires the complete public contextual criteria in the configuration UI, and those values are pinned in provenance.

## Explicitly not promoted in Plan 9

AgencityLab 1.1.3 retains several historical compatibility diagnostics. Studio does not silently promote them into the Plan 9 primary scientific layer:

- z-score outlier events on `b` are legacy compatibility diagnostics;
- derivative/rolling-variance transition detection on `b` is legacy heuristic compatibility;
- rolling-variance regime-change detection is historical heuristic compatibility;
- filtered `D` peaks requiring the optional SciPy extra are not enabled by Studio;
- multiscale signatures and tau/window sensitivity are reserved for Plan 10;
- Studio does not invent a closed-contour declaration for finite-record winding.

These omissions are intentional scientific boundaries, not missing formulas to be recreated in Studio.

## DiagnosticRun

A DiagnosticRun belongs to one exact canonical AnalysisRun. It pins:

- canonical AnalysisRun UUID;
- canonical result SHA-256;
- diagnostic public API identifiers;
- complete diagnostic configuration;
- AgencityLab version;
- AgencityStudio version;
- Python version;
- diagnostic schema version;
- deterministic diagnostic execution fingerprint;
- creator and operational timestamps.

Completed, failed, and cancelled DiagnosticRuns are immutable. Changing any threshold or diagnostic configuration creates another DiagnosticRun.

## Execution

The worker receives only the DiagnosticRun UUID. Before calling Lab it verifies that the pinned canonical result SHA still matches the canonical Run and reads the canonical artifact with SHA verification.

No canonical `compute_agencity()` call is made for visualization or diagnostics. Plan 9 reconstructs only the public `AgencityResult` data container from stored canonical arrays, including the exact stored `theta`, then calls the public `analyze_agencity()` function.

The worker uses row locks and status guards so duplicate Celery delivery cannot publish competing artifacts. Scientific validation errors are not automatically retried as if they were transient infrastructure failures.

## Diagnostic artifact

Diagnostic results use a private immutable `ZIP_JSON` schema. The archive contains a machine-readable manifest and the public diagnostic report. Its SHA-256 is distinct from both the canonical result SHA and the diagnostic execution fingerprint.

Lab diagnostics can legitimately contain `NaN` where a numerical quantity is undefined. Studio serializes non-finite values with explicit reversible JSON tags and uses strict `allow_nan=False`; it does not silently replace them with zero or another scientific value.

PostgreSQL stores ownership, lifecycle, fingerprints, configuration and artifact references. Long diagnostic series are not copied into one SQL row per sample.

## Workspace and synchronization

The Diagnostic Workspace visibly presents the two layers:

```text
CANONICAL AnalysisRun -> DIAGNOSTIC DiagnosticRun
```

Available sections are:

- Overview;
- Coherence & Orientation;
- Geometry & Topology;
- Events & Transitions;
- Regimes;
- Real Agencity.

Diagnostic series are read from the diagnostic artifact and synchronized with the canonical original sample index. Display decimation is presentation-only and preserves original indices. Selecting a diagnostic sample can therefore open the Plan 8 canonical workspace at the same exact sample.

ECharts remains the only chart engine. Browser JavaScript performs display synchronization only; it does not calculate coherence, curvature, winding, events, regimes or real-agencity criteria.

## Negative and undetermined results

The following are first-class valid software results:

- no event detected;
- no structural plateau configured/detected;
- no theta-jump diagnostic configured/detected;
- undefined winding for an open record;
- `undetermined` real-agencity assessment without contextual thresholds;
- `undetermined` non-null regime without contextual RegimeCriteria.

Studio does not change theory, canonical parameters or diagnostic settings merely to produce a positive label.

## Permissions and privacy

Workspace permissions are reused; Plan 9 creates no diagnostic ACL.

- Owner: view and run diagnostics;
- Editor: view and run diagnostics;
- Analyst: view, configure, run and rerun diagnostics;
- Viewer: inspect completed diagnostics only;
- non-member: object endpoints return 404.

Diagnostic artifacts and numeric visualization endpoints are private. No filesystem storage path is sent to the browser.

## Reproducibility tests

The primary scientific software test compares:

```text
direct AgencityLab analyze_agencity(public_result)
```

against:

```text
Studio -> labbridge diagnostics -> AgencityLab analyze_agencity(public_result)
```

for the same immutable canonical arrays and diagnostic configuration. Studio does not create expected diagnostic values by reproducing Lab formulas.

The suite also protects canonical `Theta != arg(beta)` cases, absence of invented thresholds, explicit-threshold provenance, canonical artifact immutability, diagnostic artifact integrity, duplicate task delivery, workspace isolation and role permissions.

## Scope after Plan 9

Window sensitivity, tau multiscale exploration, agencity spectra and scale comparisons belong to Plan 10. A multiscale peak will not automatically be interpreted as the true physical `tau`.
