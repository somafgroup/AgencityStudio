"""Accessible form for the AgencityLab 1.1.3 multivariate Analysis contract."""

from __future__ import annotations

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from systems.models import ObservableDefinition, ParameterOrigin, SystemRevision

from .models import SourceType
from .multivariate_validation import (
    PARAMETER_MODE_COMPONENT_VECTOR,
    PARAMETER_MODE_SYSTEM_GLOBAL,
    WINDOW_MODE_COMPONENT_VECTOR,
    WINDOW_MODE_SYSTEM_GLOBAL,
    WINDOW_MODE_UNSPECIFIED,
)
from .sources import descriptor_for


PARAMETER_MODE_CHOICES = (
    (PARAMETER_MODE_SYSTEM_GLOBAL, _("Use System Revision value for all components")),
    (PARAMETER_MODE_COMPONENT_VECTOR, _("Explicit value per component")),
)
WINDOW_MODE_CHOICES = (
    (WINDOW_MODE_UNSPECIFIED, _("Unspecified — pass w=None to AgencityLab")),
    (WINDOW_MODE_SYSTEM_GLOBAL, _("Use explicit System Revision w for all components")),
    (WINDOW_MODE_COMPONENT_VECTOR, _("Explicit w per component")),
)


def _source_descriptor(analysis):
    config = dict(analysis.draft_configuration or {})
    source_type, source_id = config.get("source_type"), config.get("source_id")
    if source_type == SourceType.RAW_DATASET_VERSION:
        from datasets.models import DatasetVersion

        source = DatasetVersion.objects.prefetch_related("columns").get(
            pk=source_id,
            dataset__project=analysis.project,
        )
        return descriptor_for(dataset_version=source)
    if source_type == SourceType.PREPARED_DATA:
        from datasets.models import PreparedDataArtifact

        source = PreparedDataArtifact.objects.select_related(
            "preparation",
            "preparation__source_version__dataset",
        ).get(
            pk=source_id,
            preparation__source_version__dataset__project=analysis.project,
        )
        return descriptor_for(prepared_artifact=source)
    return None


class MultivariateConfigurationForm(forms.Form):
    coordinate_position = forms.ChoiceField(label=_("Shared coordinate / time column"))
    system_revision = forms.ModelChoiceField(
        label=_("System Revision"),
        queryset=SystemRevision.objects.none(),
    )
    component_count = forms.IntegerField(label=_("Number of components"), min_value=1)
    a_ref_mode = forms.ChoiceField(label=_("A_ref contract"), choices=PARAMETER_MODE_CHOICES)
    tau_mode = forms.ChoiceField(label=_("tau contract"), choices=PARAMETER_MODE_CHOICES)
    w_mode = forms.ChoiceField(label=_("w contract"), choices=WINDOW_MODE_CHOICES)
    p_c_mode = forms.ChoiceField(label=_("P_c contract"), choices=PARAMETER_MODE_CHOICES)

    def __init__(self, *args, analysis, **kwargs):
        super().__init__(*args, **kwargs)
        self.analysis = analysis
        config = dict(analysis.draft_configuration or {})
        descriptor = _source_descriptor(analysis)
        column_choices = []
        if descriptor:
            for column in descriptor.column_metadata:
                label = (
                    f"{column['position']}. "
                    f"{column.get('display_name') or column.get('source_name') or 'Column'}"
                )
                if column.get("unit"):
                    label += f" [{column['unit']}]"
                column_choices.append((str(column["position"]), label))
        self.fields["coordinate_position"].choices = column_choices
        self.fields["system_revision"].queryset = (
            SystemRevision.objects.filter(system__project=analysis.project)
            .select_related("system")
            .order_by("system__name", "-revision_number")
        )
        maximum = int(getattr(settings, "MULTIVARIATE_MAX_COMPONENTS", 12))
        self.fields["component_count"].max_value = maximum
        existing = list(config.get("components") or [])
        if self.is_bound:
            try:
                count = min(max(int(self.data.get("component_count", 1)), 1), maximum)
            except (TypeError, ValueError):
                count = 1
        else:
            count = len(existing) or 2
            self.initial.update(
                {
                    "coordinate_position": config.get("coordinate_position"),
                    "system_revision": config.get("system_revision_id"),
                    "component_count": count,
                    "a_ref_mode": (config.get("parameter_modes") or {}).get(
                        "A_ref", PARAMETER_MODE_SYSTEM_GLOBAL
                    ),
                    "tau_mode": (config.get("parameter_modes") or {}).get(
                        "tau", PARAMETER_MODE_SYSTEM_GLOBAL
                    ),
                    "w_mode": (config.get("parameter_modes") or {}).get(
                        "w", WINDOW_MODE_UNSPECIFIED
                    ),
                    "p_c_mode": (config.get("parameter_modes") or {}).get(
                        "P_c", PARAMETER_MODE_SYSTEM_GLOBAL
                    ),
                }
            )
        observable_queryset = (
            ObservableDefinition.objects.filter(revision__system__project=analysis.project)
            .select_related("revision", "revision__system")
            .order_by("revision__system__name", "revision__revision_number", "position")
        )
        origin_choices = [("", _("Select origin")), *ParameterOrigin.choices]
        for index in range(1, count + 1):
            self.fields[f"component_{index}_source_position"] = forms.ChoiceField(
                label=_("Component %(number)s source column") % {"number": index},
                choices=column_choices,
            )
            self.fields[f"component_{index}_observable"] = forms.ModelChoiceField(
                label=_("Component %(number)s System observable") % {"number": index},
                queryset=observable_queryset,
            )
            for key, label in (
                ("A_ref", "A_ref"),
                ("tau", "tau"),
                ("w", "w"),
                ("P_c", "P_c"),
            ):
                prefix = f"component_{index}_{key}"
                self.fields[f"{prefix}_value"] = forms.CharField(
                    label=_("Component %(number)s %(parameter)s value")
                    % {"number": index, "parameter": label},
                    required=False,
                    max_length=80,
                )
                self.fields[f"{prefix}_unit"] = forms.CharField(
                    label=_("Component %(number)s %(parameter)s unit")
                    % {"number": index, "parameter": label},
                    required=False,
                    max_length=80,
                )
                self.fields[f"{prefix}_origin"] = forms.ChoiceField(
                    label=_("Component %(number)s %(parameter)s origin")
                    % {"number": index, "parameter": label},
                    required=False,
                    choices=origin_choices,
                )
                self.fields[f"{prefix}_justification"] = forms.CharField(
                    label=_("Component %(number)s %(parameter)s justification")
                    % {"number": index, "parameter": label},
                    required=False,
                    widget=forms.Textarea(attrs={"rows": 2}),
                )
            if index <= len(existing) and not self.is_bound:
                item = existing[index - 1]
                self.initial[f"component_{index}_source_position"] = item.get("source_position")
                self.initial[f"component_{index}_observable"] = item.get("observable_id")
                for key in ("A_ref", "tau", "w", "P_c"):
                    parameter = (item.get("parameters") or {}).get(key) or {}
                    prefix = f"component_{index}_{key}"
                    self.initial[f"{prefix}_value"] = parameter.get(
                        "value", parameter.get("requested_value", "")
                    )
                    self.initial[f"{prefix}_unit"] = parameter.get("unit", "")
                    self.initial[f"{prefix}_origin"] = parameter.get("origin", "")
                    self.initial[f"{prefix}_justification"] = parameter.get(
                        "justification", ""
                    )

    def clean(self):
        cleaned = super().clean()
        revision = cleaned.get("system_revision")
        count = cleaned.get("component_count") or 0
        seen_columns: set[int] = set()
        seen_observables: set[str] = set()
        coordinate = cleaned.get("coordinate_position")
        for index in range(1, count + 1):
            source = cleaned.get(f"component_{index}_source_position")
            observable = cleaned.get(f"component_{index}_observable")
            if source:
                position = int(source)
                if str(position) == str(coordinate):
                    self.add_error(
                        f"component_{index}_source_position",
                        _("The shared coordinate cannot also be a component."),
                    )
                if position in seen_columns:
                    self.add_error(
                        f"component_{index}_source_position",
                        _("Each component must map to a distinct source column."),
                    )
                seen_columns.add(position)
            if observable:
                if revision and observable.revision_id != revision.pk:
                    self.add_error(
                        f"component_{index}_observable",
                        _("Choose an observable from the selected System Revision."),
                    )
                identity = str(observable.pk)
                if identity in seen_observables:
                    self.add_error(
                        f"component_{index}_observable",
                        _("Each component must map to a distinct System observable."),
                    )
                seen_observables.add(identity)
        return cleaned

    def component_configs(self) -> list[dict]:
        count = int(self.cleaned_data["component_count"])
        configs = []
        for index in range(1, count + 1):
            item = {
                "source_position": int(self.cleaned_data[f"component_{index}_source_position"]),
                "observable_id": str(self.cleaned_data[f"component_{index}_observable"].pk),
            }
            for key in ("A_ref", "tau", "w", "P_c"):
                prefix = f"component_{index}_{key}"
                value_text = str(self.cleaned_data.get(f"{prefix}_value") or "").strip()
                item[key] = {
                    "value": value_text,
                    "value_text": value_text,
                    "unit": str(self.cleaned_data.get(f"{prefix}_unit") or "").strip(),
                    "origin": str(self.cleaned_data.get(f"{prefix}_origin") or "").strip(),
                    "justification": str(
                        self.cleaned_data.get(f"{prefix}_justification") or ""
                    ).strip(),
                }
            configs.append(item)
        return configs

    def parameter_modes(self) -> dict:
        return {
            "A_ref": self.cleaned_data["a_ref_mode"],
            "tau": self.cleaned_data["tau_mode"],
            "w": self.cleaned_data["w_mode"],
            "P_c": self.cleaned_data["p_c_mode"],
        }
