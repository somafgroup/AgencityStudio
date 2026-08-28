"""Forms for explicit observable spatial field configuration."""

from __future__ import annotations

from django import forms
from django.db.models import F
from django.utils.translation import gettext_lazy as _

from datasets.field_source import FIELD_SOURCE_FORMAT, field_inventory
from datasets.models import DatasetImportStatus, DatasetVersion
from systems.models import ObservableDefinition, SystemRevision

from .field_contract import (
    PARAMETER_MODE_SCALAR,
    PARAMETER_MODE_SPATIAL,
    POWER_MODE_SPACETIME,
    SPATIAL_AXES_EXPLICIT,
    SPATIAL_AXES_SAMPLE_INDEX,
    WINDOW_MODE_UNSPECIFIED,
)


class FieldAnalysisStartForm(forms.Form):
    name = forms.CharField(max_length=180, label=_("Analysis name"))
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    source = forms.ModelChoiceField(
        queryset=DatasetVersion.objects.none(),
        label=_("Immutable NPZ field source"),
        empty_label=_("Select a confirmed field Dataset Version"),
    )

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source"].queryset = (
            DatasetVersion.objects.select_related("dataset")
            .filter(
                dataset__project=project,
                dataset__current_version_id=F("pk"),
                import_status=DatasetImportStatus.READY,
                source_format=FIELD_SOURCE_FORMAT,
            )
            .order_by("dataset__name", "-version_number")
        )
        self.fields["source"].label_from_instance = (
            lambda version: f"{version.dataset.name} · v{version.version_number} · {version.original_filename}"
        )


class FieldConfigurationForm(forms.Form):
    u_key = forms.ChoiceField(label=_("Observable array u"))
    t_key = forms.ChoiceField(label=_("Time coordinate array t"))
    time_axis = forms.IntegerField(initial=0, label=_("time_axis"))
    time_unit = forms.CharField(required=False, max_length=80, label=_("Time unit"))
    observable_unit = forms.CharField(required=False, max_length=80, label=_("Observable unit"))
    spatial_axes_mode = forms.ChoiceField(
        choices=(
            (SPATIAL_AXES_SAMPLE_INDEX, _("Spatial index (spatial_axes=None)")),
            (SPATIAL_AXES_EXPLICIT, _("Explicit coordinate arrays")),
        ),
        label=_("Spatial coordinates"),
    )
    spatial_axis_keys = forms.CharField(
        required=False,
        label=_("Spatial coordinate array keys"),
        help_text=_("Comma-separated, in exact spatial dimension order. Leave empty for spatial index mode."),
    )
    spatial_axis_names = forms.CharField(
        required=False,
        label=_("Spatial axis names"),
        help_text=_("Comma-separated names in the same order, for example x,y."),
    )
    spatial_axis_units = forms.CharField(
        required=False,
        label=_("Spatial axis units"),
        help_text=_("Comma-separated units. Empty entries mean no physical unit is asserted."),
    )
    system_revision = forms.ModelChoiceField(
        queryset=SystemRevision.objects.none(), label=_("System Revision")
    )
    system_observable = forms.ModelChoiceField(
        queryset=ObservableDefinition.objects.none(), label=_("Observable")
    )
    A_ref_mode = forms.ChoiceField(
        choices=((PARAMETER_MODE_SCALAR, _("Scalar from System Revision")), (PARAMETER_MODE_SPATIAL, _("Spatial map"))),
        label="A_ref",
    )
    A_ref_map_key = forms.ChoiceField(required=False, label=_("A_ref spatial map array"))
    A_ref_map_provenance = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}), label=_("A_ref map physical provenance")
    )
    tau_mode = forms.ChoiceField(
        choices=((PARAMETER_MODE_SCALAR, _("Scalar from System Revision")), (PARAMETER_MODE_SPATIAL, _("Spatial map"))),
        label="tau",
    )
    tau_map_key = forms.ChoiceField(required=False, label=_("tau spatial map array"))
    tau_map_provenance = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}), label=_("tau map physical provenance")
    )
    w_mode = forms.ChoiceField(
        choices=(
            (WINDOW_MODE_UNSPECIFIED, _("Unspecified (w=None)")),
            (PARAMETER_MODE_SCALAR, _("Scalar from System Revision")),
            (PARAMETER_MODE_SPATIAL, _("Spatial map")),
        ),
        label="w",
    )
    w_map_key = forms.ChoiceField(required=False, label=_("w spatial map array"))
    w_map_provenance = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}), label=_("w map physical provenance")
    )
    P_c_mode = forms.ChoiceField(
        choices=(
            (PARAMETER_MODE_SCALAR, _("Scalar from System Revision")),
            (PARAMETER_MODE_SPATIAL, _("Spatial map")),
            (POWER_MODE_SPACETIME, _("Space-time map (exact u shape)")),
        ),
        label="P_c",
    )
    P_c_map_key = forms.ChoiceField(required=False, label=_("P_c map array"))
    P_c_map_provenance = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}), label=_("P_c map physical provenance")
    )
    field_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label=_("Field metadata / source description"),
    )

    def __init__(self, *args, analysis, **kwargs):
        super().__init__(*args, **kwargs)
        self.analysis = analysis
        version = DatasetVersion.objects.select_related("dataset").get(
            pk=analysis.draft_configuration.get("source_id"), dataset__project=analysis.project
        )
        inventory = field_inventory(version)
        choices = [(item["key"], f"{item['key']} · shape={tuple(item['shape'])} · {item['dtype']}") for item in inventory]
        self.fields["u_key"].choices = choices
        self.fields["t_key"].choices = choices
        for name in ("A_ref_map_key", "tau_map_key", "w_map_key", "P_c_map_key"):
            self.fields[name].choices = [("", _("Select an array")), *choices]
        self.fields["system_revision"].queryset = SystemRevision.objects.select_related("system").filter(
            system__project=analysis.project
        ).order_by("system__name", "-revision_number")
        self.fields["system_observable"].queryset = ObservableDefinition.objects.select_related(
            "revision", "revision__system"
        ).filter(revision__system__project=analysis.project).order_by(
            "revision__system__name", "revision__revision_number", "position"
        )
        initial = dict(analysis.draft_configuration or {})
        if initial.get("configured"):
            for name in self.fields:
                if name in initial:
                    self.initial[name] = initial[name]
            if initial.get("system_revision_id"):
                self.initial["system_revision"] = initial["system_revision_id"]
            if initial.get("system_observable_id"):
                self.initial["system_observable"] = initial["system_observable_id"]
            self.initial["spatial_axis_keys"] = ",".join(initial.get("spatial_axis_keys", []))
            self.initial["spatial_axis_names"] = ",".join(initial.get("spatial_axis_names", []))
            self.initial["spatial_axis_units"] = ",".join(initial.get("spatial_axis_units", []))

    @staticmethod
    def _csv(value: str) -> list[str]:
        return [part.strip() for part in str(value or "").split(",") if part.strip()]

    def clean(self):
        cleaned = super().clean()
        revision = cleaned.get("system_revision")
        observable = cleaned.get("system_observable")
        if revision and observable and observable.revision_id != revision.pk:
            self.add_error("system_observable", _("The observable must belong to the selected System Revision."))
        cleaned["spatial_axis_keys"] = self._csv(cleaned.get("spatial_axis_keys", ""))
        cleaned["spatial_axis_names"] = self._csv(cleaned.get("spatial_axis_names", ""))
        units_raw = str(cleaned.get("spatial_axis_units", ""))
        cleaned["spatial_axis_units"] = [part.strip() for part in units_raw.split(",")] if units_raw else []
        for parameter in ("A_ref", "tau", "w", "P_c"):
            mode = cleaned.get(f"{parameter}_mode")
            if mode in {PARAMETER_MODE_SPATIAL, POWER_MODE_SPACETIME}:
                if not cleaned.get(f"{parameter}_map_key"):
                    self.add_error(f"{parameter}_map_key", _("Select the explicit parameter map array."))
                if not str(cleaned.get(f"{parameter}_map_provenance", "")).strip():
                    self.add_error(
                        f"{parameter}_map_provenance",
                        _("Document the physical/contextual provenance of this parameter map."),
                    )
        return cleaned
