"""Accessible forms for the canonical Analysis configuration workflow."""

from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from datasets.models import DatasetImportStatus, DatasetVersion, PreparedDataArtifact
from systems.models import ObservableDefinition, SystemRevision

from .models import SourceType
from .sources import descriptor_for


class AnalysisStartForm(forms.Form):
    name = forms.CharField(label=_("Analysis name"), max_length=180)
    description = forms.CharField(label=_("Description"), required=False, widget=forms.Textarea(attrs={"rows": 3}))
    source = forms.ChoiceField(label=_("Data source"))

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        choices = []
        raw = (
            DatasetVersion.objects.filter(dataset__project=project, import_status=DatasetImportStatus.READY)
            .select_related("dataset")
            .order_by("dataset__name", "-version_number")
        )
        for version in raw:
            choices.append((f"{SourceType.RAW_DATASET_VERSION}:{version.pk}", _("Original: %(dataset)s · v%(version)s") % {"dataset": version.dataset.name, "version": version.version_number}))
        prepared = (
            PreparedDataArtifact.objects.filter(preparation__source_version__dataset__project=project, preparation__status="READY")
            .select_related("preparation", "preparation__source_version__dataset")
            .order_by("preparation__name")
        )
        for artifact in prepared:
            choices.append((f"{SourceType.PREPARED_DATA}:{artifact.pk}", _("Prepared: %(name)s") % {"name": artifact.preparation.name}))
        self.fields["source"].choices = choices

    def clean_source(self):
        value = self.cleaned_data["source"]
        try:
            source_type, source_id = value.split(":", 1)
        except ValueError as exc:
            raise forms.ValidationError(_("Select a valid analysis source.")) from exc
        if source_type not in SourceType.values:
            raise forms.ValidationError(_("Select a supported analysis source."))
        return source_type, source_id


class AnalysisConfigurationForm(forms.Form):
    coordinate_position = forms.ChoiceField(label=_("Coordinate / time column"))
    observable_position = forms.ChoiceField(label=_("Observable column"))
    system_revision = forms.ModelChoiceField(label=_("System Revision"), queryset=SystemRevision.objects.none())
    system_observable = forms.ModelChoiceField(label=_("System observable"), queryset=ObservableDefinition.objects.none())
    domain = forms.CharField(label=_("Domain"), required=False, max_length=160)
    mechanism = forms.CharField(label=_("Mechanism"), required=False, widget=forms.Textarea(attrs={"rows": 2}))
    system_type = forms.CharField(label=_("System type"), required=False, max_length=160)
    environment = forms.CharField(label=_("Environment"), required=False, max_length=160)
    geometry = forms.CharField(label=_("Geometry"), required=False, max_length=160)

    def __init__(self, *args, analysis, **kwargs):
        super().__init__(*args, **kwargs)
        config = dict(analysis.draft_configuration or {})
        source_type, source_id = config.get("source_type"), config.get("source_id")
        if source_type == SourceType.RAW_DATASET_VERSION:
            source = DatasetVersion.objects.prefetch_related("columns").get(pk=source_id, dataset__project=analysis.project)
            descriptor = descriptor_for(dataset_version=source)
        elif source_type == SourceType.PREPARED_DATA:
            source = PreparedDataArtifact.objects.select_related("preparation", "preparation__source_version__dataset").get(
                pk=source_id, preparation__source_version__dataset__project=analysis.project
            )
            descriptor = descriptor_for(prepared_artifact=source)
        else:
            descriptor = None
        column_choices = []
        if descriptor:
            for column in descriptor.column_metadata:
                label = f"{column['position']}. {column.get('display_name') or column.get('source_name') or 'Column'}"
                if column.get("unit"):
                    label += f" [{column['unit']}]"
                column_choices.append((str(column["position"]), label))
        self.fields["coordinate_position"].choices = column_choices
        self.fields["observable_position"].choices = column_choices
        revisions = SystemRevision.objects.filter(system__project=analysis.project).select_related("system").order_by("system__name", "-revision_number")
        self.fields["system_revision"].queryset = revisions
        self.fields["system_observable"].queryset = ObservableDefinition.objects.filter(revision__system__project=analysis.project).select_related("revision", "revision__system")
        if not self.is_bound and config.get("coordinate_position"):
            self.initial.update(
                {
                    "coordinate_position": config.get("coordinate_position"),
                    "observable_position": config.get("observable_position"),
                    "system_revision": config.get("system_revision_id"),
                    "system_observable": config.get("system_observable_id"),
                    **dict(config.get("options") or {}),
                }
            )

    def clean(self):
        cleaned = super().clean()
        revision = cleaned.get("system_revision")
        observable = cleaned.get("system_observable")
        if revision and observable and observable.revision_id != revision.pk:
            self.add_error("system_observable", _("Choose an observable from the selected System Revision."))
        return cleaned
