"""Presentation registry for AgencityLab 1.1.3 public diagnostic outputs.

The registry names public Lab outputs and UI groups only. It contains no formula,
classifier, threshold, or fallback diagnostic implementation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiagnosticDescriptor:
    key: str
    label: str
    public_api: str
    group: str
    scientific_status: str
    configuration: str


STANDARD_PUBLIC_API = "agencitylab.analyze_agencity"

SUPPORTED_DIAGNOSTICS: tuple[DiagnosticDescriptor, ...] = (
    DiagnosticDescriptor(
        "structural_orientation",
        "Coherence & orientation",
        STANDARD_PUBLIC_API,
        "coherence",
        "DIAGNOSTIC / theory-derived Sigma_Theta",
        "No universal threshold; canonical Theta is consumed directly.",
    ),
    DiagnosticDescriptor(
        "real_agencity",
        "Real-agencity evidence",
        STANDARD_PUBLIC_API,
        "coherence",
        "DIAGNOSTIC",
        "Contextual Sigma_Theta and |b| thresholds are optional; without them status is undetermined.",
    ),
    DiagnosticDescriptor(
        "geometry",
        "Geometry & topology",
        STANDARD_PUBLIC_API,
        "geometry",
        "DIAGNOSTIC",
        "Curvature is computed by Lab on beta; finite-record winding is not forced closed.",
    ),
    DiagnosticDescriptor(
        "dynamic_peaks",
        "Dynamic-intensity peaks",
        STANDARD_PUBLIC_API,
        "events",
        "DIAGNOSTIC",
        "Unfiltered public NumPy-only peak detector; no Studio prominence threshold.",
    ),
    DiagnosticDescriptor(
        "zeros",
        "Canonical zero condition",
        STANDARD_PUBLIC_API,
        "events",
        "DIAGNOSTIC / exact theory condition",
        "Lab exact zero condition with atol=0 in the standard report.",
    ),
    DiagnosticDescriptor(
        "critical_surface",
        "Critical surface D = S",
        STANDARD_PUBLIC_API,
        "events",
        "DIAGNOSTIC / theory-facing transition",
        "Exact samples and sign-change crossings; no near-zero Studio threshold.",
    ),
    DiagnosticDescriptor(
        "theta_jumps",
        "Theta jumps",
        STANDARD_PUBLIC_API,
        "events",
        "DIAGNOSTIC",
        "Optional explicit angular threshold; absent means not configured.",
    ),
    DiagnosticDescriptor(
        "structural_plateaus",
        "Structural plateaus",
        STANDARD_PUBLIC_API,
        "events",
        "DIAGNOSTIC",
        "Optional explicit slope threshold and minimum duration; both are required together.",
    ),
    DiagnosticDescriptor(
        "regime_signature",
        "Regime signature",
        STANDARD_PUBLIC_API,
        "regimes",
        "DIAGNOSTIC / threshold-free signature",
        "No classification threshold is required for the signature itself.",
    ),
    DiagnosticDescriptor(
        "regime_classification",
        "Regime classification",
        STANDARD_PUBLIC_API,
        "regimes",
        "DIAGNOSTIC",
        "Non-null classification requires explicit contextual RegimeCriteria; otherwise undetermined.",
    ),
)

DEFERRED_OR_LEGACY: tuple[dict[str, str], ...] = (
    {
        "key": "legacy_b_outliers",
        "reason": "Lab labels the b z-score detector legacy diagnostic compatibility; Studio does not promote it as a Plan 9 primary diagnostic.",
    },
    {
        "key": "legacy_b_transition_heuristic",
        "reason": "Lab labels the derivative/variance transition detector legacy heuristic compatibility.",
    },
    {
        "key": "legacy_regime_changes",
        "reason": "Lab labels rolling-variance regime-change detection historical heuristic and excludes it from the theory-facing classifier.",
    },
    {
        "key": "filtered_dynamic_peaks",
        "reason": "Lab 1.1.3 requires its optional SciPy scientific extra for prominence/distance filtering; Studio adds no scientific dependency in Plan 9.",
    },
    {
        "key": "multiscale_signature",
        "reason": "Multiscale and tau/window sensitivity are reserved for Plan 10.",
    },
    {
        "key": "closed_winding_declaration",
        "reason": "The standard Lab report treats a finite AnalysisRun as open; Studio does not invent closure. Net phase turns and the explicit undefined winding diagnostic remain visible.",
    },
)
