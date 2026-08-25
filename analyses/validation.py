"""Structural and numerical-contract preflight for canonical Analysis execution.

These checks explain known AgencityLab 1.1.3 input requirements early. They do
not calculate any Agencity quantity and AgencityLab remains authoritative.
"""

from __future__ import annotations

import math

import numpy as np
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from common.units import inspect_unit, units_are_compatible
from systems.models import MemoryWindowMode

from .sources import SourceContractError, column_at


class PreflightError(SourceContractError):
    """Blocking execution-contract error with no implicit source modification."""


def validate_mapping(
    descriptor, *, coordinate_position: int, observable_position: int
) -> tuple[dict, dict]:
    coordinate = column_at(descriptor, coordinate_position)
    observable = column_at(descriptor, observable_position)
    for label, column in (("coordinate", coordinate), ("observable", observable)):
        if column.get("inferred_type") != "NUMERIC":
            raise PreflightError(
                f"The selected {label} column must be numeric for canonical scalar analysis."
            )
        if (
            int(column.get("missing_count", 0))
            or int(column.get("non_numeric_count", 0))
            or int(column.get("non_finite_count", 0))
        ):
            raise PreflightError(
                f"The selected {label} column contains missing, non-numeric or non-finite values. "
                "Prepare the data explicitly before analysis."
            )
    return coordinate, observable


def _require_exact_execution_unit(
    source_unit: str, context_unit: str, label: str
) -> list[dict]:
    source = str(source_unit or "").strip()
    context = str(context_unit or "").strip()
    if not source or not context:
        raise PreflightError(
            f"{label} unit metadata must be explicit before canonical execution."
        )
    if source == context:
        info = inspect_unit(source)
        return (
            []
            if info.recognized
            else [
                {
                    "code": "UNKNOWN_UNIT",
                    "message": (
                        f"Unit {source!r} is preserved but Studio cannot dimensionally verify it."
                    ),
                }
            ]
        )
    compatible = units_are_compatible(source, context)
    if compatible is True:
        raise PreflightError(
            f"{label} uses {source!r} while the System context uses {context!r}. "
            "No unit conversion occurs during analysis; create explicit Prepared Data with the "
            "required unit."
        )
    if compatible is False:
        raise PreflightError(
            f"{label} unit {source!r} is dimensionally incompatible with System unit {context!r}."
        )
    raise PreflightError(
        f"{label} unit labels {source!r} and {context!r} do not match and cannot be safely "
        "verified. Prepare or document matching units before analysis."
    )


def validate_units(
    *, coordinate: dict, observable: dict, revision, system_observable
) -> list[dict]:
    warnings: list[dict] = []
    warnings.extend(
        _require_exact_execution_unit(
            observable.get("unit", ""), system_observable.unit, "Observable"
        )
    )
    warnings.extend(
        _require_exact_execution_unit(
            observable.get("unit", ""), revision.a_ref_unit, "Observable/A_ref"
        )
    )
    warnings.extend(
        _require_exact_execution_unit(
            coordinate.get("unit", ""), revision.tau_unit, "Coordinate/tau"
        )
    )
    if revision.w_mode == MemoryWindowMode.EXPLICIT:
        warnings.extend(
            _require_exact_execution_unit(
                coordinate.get("unit", ""), revision.w_unit, "Coordinate/w"
            )
        )
    return warnings


def validate_parameter_contract(revision) -> dict:
    if revision.a_ref_value is None:
        raise PreflightError(
            "A_ref is required for canonical execution; revise the System context explicitly."
        )
    if revision.tau_value is None:
        raise PreflightError(
            "tau is required for canonical execution; revise the System context explicitly."
        )
    if revision.p_c_value is None:
        raise PreflightError(
            "P_c is required for canonical execution; revise the System context explicitly."
        )
    if revision.a_ref_value <= 0 or revision.tau_value <= 0:
        raise PreflightError("A_ref and tau must be strictly positive.")
    if revision.p_c_value < 0:
        raise PreflightError("P_c must be non-negative; P_c = 0 is valid.")
    requested_w = None
    if revision.w_mode == MemoryWindowMode.EXPLICIT:
        if revision.w_value is None or revision.w_value <= 0:
            raise PreflightError("Explicit w must be strictly positive.")
        requested_w = float(revision.w_value)
    return {
        "A_ref": {
            "value": float(revision.a_ref_value),
            "value_text": revision.a_ref_value_text,
            "unit": revision.a_ref_unit,
            "origin": revision.a_ref_origin,
            "origin_detail": revision.a_ref_origin_detail,
            "justification": revision.a_ref_justification,
            "source": "SYSTEM_VALUE",
        },
        "tau": {
            "value": float(revision.tau_value),
            "value_text": revision.tau_value_text,
            "unit": revision.tau_unit,
            "origin": revision.tau_origin,
            "origin_detail": revision.tau_origin_detail,
            "justification": revision.tau_justification,
            "source": "SYSTEM_VALUE",
        },
        "w": {
            "mode": revision.w_mode,
            "requested_value": requested_w,
            "value_text": revision.w_value_text,
            "unit": revision.w_unit,
            "origin": revision.w_origin,
            "origin_detail": revision.w_origin_detail,
            "justification": revision.w_justification,
            "source": "SYSTEM_VALUE",
        },
        "P_c": {
            "value": float(revision.p_c_value),
            "value_text": revision.p_c_value_text,
            "unit": revision.p_c_unit,
            "origin": revision.p_c_origin,
            "origin_detail": revision.p_c_origin_detail,
            "justification": revision.p_c_justification,
            "source": "SYSTEM_VALUE",
        },
    }


def validate_sample_contract(
    xi: np.ndarray,
    u: np.ndarray,
    *,
    requested_w: float | None,
    tau: float,
) -> None:
    """Explain public Lab/CRM coordinate constraints without altering the vectors.

    ``tau`` is deliberately not substituted for an unspecified ``w`` here. When
    ``requested_w`` is ``None``, Studio preserves that public API request and lets
    AgencityLab resolve and validate its implementation convention authoritatively.
    """
    del tau
    if xi.ndim != 1 or u.ndim != 1 or len(xi) != len(u):
        raise PreflightError(
            "Coordinate and observable must be one-dimensional arrays of equal length."
        )
    if len(xi) < 3:
        raise PreflightError("Canonical scalar analysis requires at least three samples.")
    if not np.isfinite(xi).all() or not np.isfinite(u).all():
        raise PreflightError(
            "Canonical scalar analysis requires finite coordinate and observable values."
        )
    diffs = np.diff(xi)
    if np.any(diffs <= 0):
        raise PreflightError(
            "The selected coordinate is not strictly increasing. "
            "Prepare the data explicitly before analysis."
        )
    step = float(diffs[0])
    atol = float(np.finfo(float).eps * max(1.0, abs(step)) * 64.0)
    if not np.allclose(diffs, step, rtol=1e-10, atol=atol):
        raise PreflightError(
            "The selected coordinate is irregularly sampled. Create explicit Prepared Data with "
            "resampling before canonical analysis."
        )
    if requested_w is None:
        return
    window = float(requested_w)
    samples = round(window / step)
    if samples < 1:
        raise PreflightError("The requested CRM window is smaller than one sampling interval.")
    represented = samples * step
    tolerance = max(
        np.finfo(float).eps * max(1.0, abs(window)) * 128.0,
        abs(step) * 1e-9,
    )
    if not math.isclose(
        represented, window, rel_tol=1e-9, abs_tol=float(tolerance)
    ):
        raise PreflightError(
            "The requested CRM window is not an integer multiple of the sampling interval. "
            "Studio will not modify w; prepare compatible data or revise the explicit scientific "
            "context."
        )
    if len(xi) < 2 * samples:
        raise PreflightError(
            "The selected signal is too short for two CRM windows under this configuration."
        )


def as_django_validation(exc: SourceContractError) -> ValidationError:
    return ValidationError(_(str(exc)))
