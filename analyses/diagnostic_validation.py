"""Structural validation for public AgencityLab diagnostic configuration.

Values are validated against the public Lab argument contracts only. This module
contains no diagnostic equations, classifications, or scientific thresholds.
"""

from __future__ import annotations

import math

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


_REQUIRED_REGIME = (
    "sigma_theta_low_max",
    "sigma_theta_high_min",
    "tail_cv_max",
    "unstable_growth_ratio_min",
    "curvature_zero_max",
    "periodicity_min",
)
_OPTIONAL_REGIME = (
    "weak_structure_max",
    "weak_beta_variance_max",
    "structure_variability_min",
)


def _optional_number(value, *, name: str, maximum: float | None = None) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(_("%(name)s must be numeric.") % {"name": name}) from exc
    if not math.isfinite(number) or number < 0.0:
        raise ValidationError(_("%(name)s must be finite and non-negative.") % {"name": name})
    if maximum is not None and number > maximum:
        raise ValidationError(
            _("%(name)s must not exceed %(maximum)s.")
            % {"name": name, "maximum": maximum}
        )
    return number


def normalize_diagnostic_configuration(configuration: dict | None) -> dict:
    """Return the exact supported configuration without inventing defaults."""
    source = dict(configuration or {})
    if source.get("bundle", "standard_public_diagnostics") != "standard_public_diagnostics":
        raise ValidationError(_("Unsupported diagnostic bundle."))

    real_source = dict(source.get("real_agencity") or {})
    real = {
        "s_threshold": _optional_number(real_source.get("s_threshold"), name="S_min"),
        "theta_variance_threshold": _optional_number(
            real_source.get("theta_variance_threshold"), name="Sigma_Theta maximum"
        ),
        "b_threshold": _optional_number(real_source.get("b_threshold"), name="|b| minimum"),
        "min_fraction": _optional_number(
            real_source.get("min_fraction"), name="minimum fraction", maximum=1.0
        ),
    }
    if real["min_fraction"] is not None and (
        real["theta_variance_threshold"] is None or real["b_threshold"] is None
    ):
        raise ValidationError(
            _("A global real-agencity fraction requires both local Sigma_Theta and |b| thresholds.")
        )

    jump_source = dict(source.get("theta_jumps") or {})
    jumps = {
        "threshold": _optional_number(
            jump_source.get("threshold"), name="Theta jump threshold", maximum=math.pi
        )
    }

    plateau_source = dict(source.get("structural_plateaus") or {})
    plateaus = {
        "slope_threshold": _optional_number(
            plateau_source.get("slope_threshold"), name="plateau slope threshold"
        ),
        "min_duration": _optional_number(
            plateau_source.get("min_duration"), name="plateau minimum duration"
        ),
    }
    if (plateaus["slope_threshold"] is None) != (plateaus["min_duration"] is None):
        raise ValidationError(
            _("Structural plateau slope threshold and minimum duration must be provided together.")
        )

    regime_source = dict(source.get("regime_criteria") or {})
    enabled = bool(regime_source.get("enabled", False))
    regime: dict[str, object] = {"enabled": enabled}
    if enabled:
        for name in _REQUIRED_REGIME:
            value = _optional_number(
                regime_source.get(name),
                name=name,
                maximum=1.0 if name == "periodicity_min" else None,
            )
            if value is None:
                raise ValidationError(
                    _("All required contextual regime criteria must be supplied when classification is enabled.")
                )
            regime[name] = value
        for name in _OPTIONAL_REGIME:
            regime[name] = _optional_number(regime_source.get(name), name=name)
        if float(regime["sigma_theta_high_min"]) < float(regime["sigma_theta_low_max"]):
            raise ValidationError(
                _("Regime high Sigma_Theta minimum must be greater than or equal to the low maximum.")
            )

    return {
        "bundle": "standard_public_diagnostics",
        "real_agencity": real,
        "theta_jumps": jumps,
        "structural_plateaus": plateaus,
        "regime_criteria": regime,
        "dynamic_peaks": {
            "mode": "unfiltered_public_default",
            "prominence": None,
            "distance": None,
        },
        "zero_detection": {"atol": 0.0, "mode": "exact_public_report"},
        "multiscale": {"enabled": False, "reason": "Plan 10"},
        "legacy_heuristics": {"enabled": False},
    }
