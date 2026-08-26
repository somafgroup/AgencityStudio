"""Accessible explicit configuration forms for Plan 10 sensitivity studies."""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .configuration import generate_grid
from .models import GridType, StudyType


class SensitivityStudyForm(forms.Form):
    study_type = forms.ChoiceField(
        label=_("Study type"),
        choices=StudyType.choices,
        help_text=_("Sensitivity studies never rewrite the physical SystemRevision."),
    )
    grid_type = forms.ChoiceField(
        label=_("Grid generation"),
        choices=GridType.choices,
    )
    explicit_values = forms.CharField(
        label=_("Explicit scale values"),
        required=False,
        help_text=_("Comma-separated positive values in the Run's coordinate-time unit."),
    )
    start = forms.FloatField(label=_("Range start"), required=False, min_value=0.0)
    stop = forms.FloatField(label=_("Range stop"), required=False, min_value=0.0)
    count = forms.IntegerField(label=_("Number of scales"), required=False, min_value=2)

    def _explicit(self) -> list[float]:
        text = str(self.cleaned_data.get("explicit_values") or "").strip()
        if not text:
            return []
        try:
            return [float(piece.strip()) for piece in text.split(",") if piece.strip()]
        except ValueError as exc:
            raise forms.ValidationError(_("Explicit scale values must be numeric.")) from exc

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        try:
            grid = generate_grid(
                grid_type=cleaned["grid_type"],
                explicit_values=self._explicit(),
                start=cleaned.get("start"),
                stop=cleaned.get("stop"),
                count=cleaned.get("count"),
            )
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc
        cleaned["generated_grid"] = grid
        return cleaned

    def study_configuration(self, *, grid_unit: str) -> dict:
        if not self.is_valid():
            raise ValueError("Sensitivity study form is not valid.")
        data = self.cleaned_data
        return {
            "study_type": data["study_type"],
            "grid_type": data["grid_type"],
            "grid_unit": str(grid_unit or ""),
            "requested_grid": list(data["generated_grid"]),
            "generation": {
                "explicit_text": str(data.get("explicit_values") or ""),
                "start": data.get("start"),
                "stop": data.get("stop"),
                "count": data.get("count"),
            },
        }
