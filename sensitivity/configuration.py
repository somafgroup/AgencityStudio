"""Explicit numerical grid contracts for sensitivity studies.

Grid generation samples parameter space only; it does not estimate physical
``tau`` or ``w`` from signal statistics.
"""

from __future__ import annotations

import math

import numpy as np
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from analyses.validation import PreflightError, validate_sample_contract

from .models import GridType, StudyType


def _finite_positive(values) -> list[float]:
    result = [float(value) for value in values]
    if not result:
        raise ValidationError(_("At least one scale value is required."))
    if any(not math.isfinite(value) or value <= 0.0 for value in result):
        raise ValidationError(_("All scale values must be strictly positive and finite."))
    if len(result) > settings.SENSITIVITY_MAX_POINTS:
        raise ValidationError(
            _("This study exceeds the configured sensitivity-point limit (%(limit)s).")
            % {"limit": settings.SENSITIVITY_MAX_POINTS}
        )
    if len(set(result)) != len(result):
        raise ValidationError(_("Scale values must be unique."))
    return result


def generate_grid(
    *,
    grid_type: str,
    explicit_values: list[float] | None = None,
    start: float | None = None,
    stop: float | None = None,
    count: int | None = None,
) -> list[float]:
    """Generate and return the exact values that will be persisted and executed."""
    if grid_type == GridType.EXPLICIT:
        return _finite_positive(explicit_values or [])
    if start is None or stop is None or count is None:
        raise ValidationError(_("Range grids require start, stop and count."))
    start = float(start)
    stop = float(stop)
    count = int(count)
    if count < 2:
        raise ValidationError(_("Range grids require at least two points."))
    if count > settings.SENSITIVITY_MAX_POINTS:
        raise ValidationError(
            _("This study exceeds the configured sensitivity-point limit (%(limit)s).")
            % {"limit": settings.SENSITIVITY_MAX_POINTS}
        )
    if not math.isfinite(start) or not math.isfinite(stop) or start <= 0.0 or stop <= 0.0:
        raise ValidationError(_("Grid start and stop must be strictly positive and finite."))
    if stop <= start:
        raise ValidationError(_("Grid stop must be greater than grid start."))
    if grid_type == GridType.LINEAR:
        return _finite_positive(np.linspace(start, stop, count, dtype=float).tolist())
    if grid_type == GridType.LOG:
        return _finite_positive(np.geomspace(start, stop, count, dtype=float).tolist())
    raise ValidationError(_("Unsupported sensitivity grid type."))


def validate_grid_against_run(*, study_type: str, grid: list[float], xi, u, run) -> None:
    """Apply known public Lab sampling constraints without modifying the grid."""
    params = run.parameter_snapshot
    if study_type == StudyType.W_SENSITIVITY:
        tau = float(params["tau"]["value"])
        for candidate in grid:
            validate_sample_contract(xi, u, requested_w=candidate, tau=tau)
        return
    if study_type == StudyType.TAU_MULTISCALE:
        requested_w = params["w"].get("requested_value")
        if params["w"].get("mode") == "UNSPECIFIED":
            validate_sample_contract(
                xi,
                u,
                requested_w=None,
                tau=float(params["tau"]["value"]),
            )
        else:
            validate_sample_contract(
                xi,
                u,
                requested_w=float(requested_w),
                tau=float(params["tau"]["value"]),
            )
        return
    raise PreflightError("Unsupported sensitivity study type.")
