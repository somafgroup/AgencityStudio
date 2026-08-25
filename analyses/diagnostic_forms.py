"""Accessible forms for explicit AgencityLab diagnostic configuration."""

from __future__ import annotations

import math

from django import forms
from django.utils.translation import gettext_lazy as _


class DiagnosticConfigurationForm(forms.Form):
    """Expose only configurable public Lab diagnostics, without Studio defaults."""

    s_threshold = forms.FloatField(
        label=_("Structural support threshold S_min"),
        required=False,
        min_value=0.0,
        help_text=_("Optional diagnostic override. If omitted, AgencityLab uses its public default S > 0."),
    )
    theta_variance_threshold = forms.FloatField(
        label=_("Maximum Sigma_Theta for local real-agencity evidence"),
        required=False,
        min_value=0.0,
        help_text=_("Contextual diagnostic threshold. The theory does not define a universal value."),
    )
    b_threshold = forms.FloatField(
        label=_("Minimum |b| for local real-agencity evidence"),
        required=False,
        min_value=0.0,
        help_text=_("Contextual diagnostic threshold. The theory does not define a universal value."),
    )
    min_fraction = forms.FloatField(
        label=_("Minimum evaluated fraction for a global assessment"),
        required=False,
        min_value=0.0,
        max_value=1.0,
        help_text=_("Optional contextual aggregation criterion in [0, 1]."),
    )
    theta_jump_threshold = forms.FloatField(
        label=_("Theta jump threshold (radians)"),
        required=False,
        min_value=0.0,
        max_value=math.pi,
        help_text=_("Optional diagnostic angle in [0, pi]. No jump threshold is assumed when blank."),
    )
    plateau_slope_threshold = forms.FloatField(
        label=_("Structural plateau slope threshold"),
        required=False,
        min_value=0.0,
        help_text=_("Optional diagnostic tolerance; must be configured with minimum duration."),
    )
    plateau_min_duration = forms.FloatField(
        label=_("Structural plateau minimum duration"),
        required=False,
        min_value=0.0,
        help_text=_("Uses the canonical coordinate unit; must be configured with slope threshold."),
    )

    enable_regime_classification = forms.BooleanField(
        label=_("Configure non-null regime classification"),
        required=False,
        help_text=_("Without contextual criteria, non-null records remain undetermined."),
    )
    sigma_theta_low_max = forms.FloatField(
        label=_("Regime: low Sigma_Theta maximum"), required=False, min_value=0.0
    )
    sigma_theta_high_min = forms.FloatField(
        label=_("Regime: high Sigma_Theta minimum"), required=False, min_value=0.0
    )
    tail_cv_max = forms.FloatField(
        label=_("Regime: tail relative RMS / convergence maximum"), required=False, min_value=0.0
    )
    unstable_growth_ratio_min = forms.FloatField(
        label=_("Regime: unstable growth ratio minimum"), required=False, min_value=0.0
    )
    curvature_zero_max = forms.FloatField(
        label=_("Regime: near-flat curvature maximum"), required=False, min_value=0.0
    )
    periodicity_min = forms.FloatField(
        label=_("Regime: periodicity minimum"), required=False, min_value=0.0, max_value=1.0
    )
    weak_structure_max = forms.FloatField(
        label=_("Regime: weak structure maximum"), required=False, min_value=0.0
    )
    weak_beta_variance_max = forms.FloatField(
        label=_("Regime: weak beta variance maximum"), required=False, min_value=0.0
    )
    structure_variability_min = forms.FloatField(
        label=_("Regime: structure variability minimum"), required=False, min_value=0.0
    )

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

    def clean(self):
        cleaned = super().clean()
        slope = cleaned.get("plateau_slope_threshold")
        duration = cleaned.get("plateau_min_duration")
        if (slope is None) != (duration is None):
            raise forms.ValidationError(
                _("Structural plateau slope threshold and minimum duration must be provided together.")
            )

        if cleaned.get("min_fraction") is not None and (
            cleaned.get("theta_variance_threshold") is None
            or cleaned.get("b_threshold") is None
        ):
            raise forms.ValidationError(
                _("A global real-agencity fraction requires both local Sigma_Theta and |b| thresholds.")
            )

        if cleaned.get("enable_regime_classification"):
            missing = [name for name in self._REQUIRED_REGIME if cleaned.get(name) is None]
            if missing:
                raise forms.ValidationError(
                    _("All required contextual regime criteria must be provided when classification is enabled.")
                )
            if cleaned["sigma_theta_high_min"] < cleaned["sigma_theta_low_max"]:
                raise forms.ValidationError(
                    _("Regime high Sigma_Theta minimum must be greater than or equal to the low maximum.")
                )
        return cleaned

    def diagnostic_configuration(self) -> dict:
        """Return a provenance-ready configuration with no invented thresholds."""
        if not self.is_valid():
            raise ValueError("Diagnostic configuration is not valid.")
        data = self.cleaned_data
        regime: dict[str, object] = {"enabled": bool(data["enable_regime_classification"])}
        if regime["enabled"]:
            for name in (*self._REQUIRED_REGIME, *self._OPTIONAL_REGIME):
                regime[name] = data.get(name)
        return {
            "bundle": "standard_public_diagnostics",
            "real_agencity": {
                "s_threshold": data.get("s_threshold"),
                "theta_variance_threshold": data.get("theta_variance_threshold"),
                "b_threshold": data.get("b_threshold"),
                "min_fraction": data.get("min_fraction"),
            },
            "theta_jumps": {"threshold": data.get("theta_jump_threshold")},
            "structural_plateaus": {
                "slope_threshold": data.get("plateau_slope_threshold"),
                "min_duration": data.get("plateau_min_duration"),
            },
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
