"""Public AgencityLab diagnostic integration for immutable canonical results.

This module rehydrates the stable public :class:`AgencityResult` container from
stored canonical arrays and delegates every scientific diagnostic to the public
AgencityLab analysis API. It never recomputes canonical or diagnostic equations.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np

from agencitylab import AgencityError, AgencityResult, analyze_agencity


DIAGNOSTIC_PUBLIC_API = "agencitylab.analyze_agencity"
DIAGNOSTIC_ANALYSIS_SCHEMA = "0.5"
REQUIRED_CANONICAL_SERIES = (
    "xi",
    "u",
    "u_star",
    "X_star",
    "A_star",
    "t_star",
    "M",
    "O",
    "D",
    "S",
    "J",
    "theta",
    "U",
    "beta",
    "b",
)


class DiagnosticLabError(RuntimeError):
    """Safe integration error raised at the Studio/Lab diagnostic boundary."""

    def __init__(self, message: str, *, category: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class DiagnosticExecution:
    """Detached public diagnostic output plus captured public warnings."""

    report: dict[str, Any]
    warnings: tuple[dict[str, str], ...]
    api_identifiers: tuple[str, ...]


def rehydrate_public_result(*, arrays: dict[str, np.ndarray], manifest: dict) -> AgencityResult:
    """Recreate only the public result container from immutable stored values.

    ``theta`` is mandatory. Allowing :class:`AgencityResult` to synthesize theta
    from U would violate Studio's Plan 8/9 orientation contract, so an artifact
    without stored canonical theta is rejected for diagnostics.
    """
    missing = [name for name in REQUIRED_CANONICAL_SERIES if name not in arrays]
    if missing:
        raise DiagnosticLabError(
            "The canonical artifact does not contain every public series required for diagnostics: "
            + ", ".join(missing),
            category="RESULT_INPUT_ERROR",
        )

    context = dict(manifest.get("result_context") or {})
    units = dict(manifest.get("units") or {})
    metadata = dict(manifest.get("lab_metadata") or {})
    if context.get("effective_w") is not None and metadata.get("memory_window") is None:
        metadata["memory_window"] = context["effective_w"]

    try:
        return AgencityResult(
            xi=arrays["xi"],
            u=arrays["u"],
            u_star=arrays["u_star"],
            X_star=arrays["X_star"],
            A_star=arrays["A_star"],
            t_star=arrays["t_star"],
            tau=context["tau"],
            P_c=context["P_c"],
            A_ref=context["A_ref"],
            M=arrays["M"],
            O=arrays["O"],
            D=arrays["D"],
            S=arrays["S"],
            J=arrays["J"],
            U=arrays["U"],
            beta=arrays["beta"],
            b=arrays["b"],
            theta=arrays["theta"],
            unit=str(units.get("observable") or ""),
            coordinate_unit=str(units.get("coordinate") or ""),
            power_unit=str(units.get("power") or ""),
            observable_kind=str(context.get("observable_kind") or ""),
            domain=str(context.get("domain") or ""),
            system_type=str(context.get("system_type") or ""),
            mechanism=str(context.get("mechanism") or ""),
            metadata=metadata,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise DiagnosticLabError(
            "The stored canonical result cannot be represented by the public AgencityLab result contract.",
            category="RESULT_INPUT_ERROR",
        ) from exc


def _real_thresholds(configuration: dict) -> dict[str, float] | None:
    source = dict(configuration.get("real_agencity") or {})
    result = {
        key: source[key]
        for key in (
            "s_threshold",
            "theta_variance_threshold",
            "b_threshold",
            "min_fraction",
        )
        if source.get(key) is not None
    }
    return result or None


def _regime_criteria(configuration: dict) -> dict[str, float] | None:
    source = dict(configuration.get("regime_criteria") or {})
    enabled = bool(source.pop("enabled", False))
    if not enabled:
        return None
    return {key: value for key, value in source.items() if value is not None}


def execute_diagnostics(
    *,
    arrays: dict[str, np.ndarray],
    manifest: dict,
    configuration: dict,
) -> DiagnosticExecution:
    """Run the public AgencityLab standard diagnostic bundle unchanged."""
    result = rehydrate_public_result(arrays=arrays, manifest=manifest)
    plateaus = dict(configuration.get("structural_plateaus") or {})
    theta_jump = dict(configuration.get("theta_jumps") or {})

    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            report = analyze_agencity(
                result,
                real_agencity_thresholds=_real_thresholds(configuration),
                regime_criteria=_regime_criteria(configuration),
                theta_jump_threshold=theta_jump.get("threshold"),
                plateau_slope_threshold=plateaus.get("slope_threshold"),
                plateau_min_duration=plateaus.get("min_duration"),
                # Keep the NumPy-only public D-peak detector. Filtered peaks in
                # Lab 1.1.3 require the optional SciPy extra, which Studio does
                # not add merely to create a diagnostic preference.
                d_peak_prominence=None,
                verbose=False,
            )
    except (TypeError, ValueError) as exc:
        raise DiagnosticLabError(
            str(exc), category="LAB_DIAGNOSTIC_VALIDATION_ERROR"
        ) from exc
    except AgencityError as exc:
        raise DiagnosticLabError(
            str(exc), category="LAB_DIAGNOSTIC_EXECUTION_ERROR"
        ) from exc
    except Exception as exc:
        raise DiagnosticLabError(
            "AgencityLab diagnostic execution failed.",
            category="LAB_DIAGNOSTIC_EXECUTION_ERROR",
        ) from exc

    warning_payload = tuple(
        {
            "category": item.category.__name__,
            "message": str(item.message),
        }
        for item in captured
    )
    return DiagnosticExecution(
        report=report,
        warnings=warning_payload,
        api_identifiers=(DIAGNOSTIC_PUBLIC_API,),
    )
