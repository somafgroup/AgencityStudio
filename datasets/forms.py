"""Forms for Dataset metadata and raw-source import configuration."""

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Dataset


class DatasetForm(forms.ModelForm):
    class Meta:
        model = Dataset
        fields = ("name", "description")
        widgets = {
            "name": forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
            "description": forms.Textarea(attrs={"class": "textarea", "rows": 4}),
        }


class ImportOptionsMixin:
    encoding = forms.CharField(
        required=False,
        label=_("Encoding"),
        widget=forms.TextInput(attrs={"class": "input", "placeholder": _("Auto-detect")}),
        help_text=_("Leave blank to detect text encoding."),
    )
    delimiter = forms.CharField(
        required=False,
        max_length=1,
        label=_("Delimiter"),
        widget=forms.TextInput(attrs={"class": "input", "placeholder": _("Auto-detect")}),
        help_text=_("Leave blank to detect. Enter one character, such as comma, semicolon or tab."),
    )
    header_mode = forms.ChoiceField(
        required=False,
        label=_("Header row"),
        choices=(("", _("Auto-detect")), ("yes", _("Yes")), ("no", _("No"))),
        widget=forms.Select(attrs={"class": "select"}),
    )
    decimal_separator = forms.ChoiceField(
        label=_("Decimal separator"),
        choices=((".", "."), (",", ",")),
        initial=".",
        widget=forms.Select(attrs={"class": "select"}),
    )
    sheet = forms.CharField(
        required=False,
        label=_("XLSX sheet"),
        widget=forms.TextInput(attrs={"class": "input", "placeholder": _("First worksheet")}),
        help_text=_("Leave blank for the first worksheet. Re-inspect later to select another sheet."),
    )

    def import_options(self) -> dict:
        mode = self.cleaned_data.get("header_mode", "")
        options = {
            "encoding": self.cleaned_data.get("encoding", "").strip(),
            "delimiter": self.cleaned_data.get("delimiter", ""),
            "decimal_separator": self.cleaned_data.get("decimal_separator", "."),
            "sheet": self.cleaned_data.get("sheet", "").strip(),
        }
        if mode:
            options["has_header"] = mode == "yes"
        return {key: value for key, value in options.items() if value not in {"", None}}


class DatasetImportForm(ImportOptionsMixin, forms.Form):
    SOURCE_UPLOAD = "upload"
    SOURCE_PASTE = "paste"
    source_mode = forms.ChoiceField(
        label=_("Source"),
        choices=((SOURCE_UPLOAD, _("Upload file")), (SOURCE_PASTE, _("Paste tabular data"))),
        initial=SOURCE_UPLOAD,
        widget=forms.RadioSelect,
    )
    name = forms.CharField(max_length=180, widget=forms.TextInput(attrs={"class": "input"}))
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "textarea", "rows": 3}),
    )
    source_file = forms.FileField(
        required=False,
        label=_("Dataset file"),
        widget=forms.ClearableFileInput(
            attrs={"class": "input", "accept": ".csv,.tsv,.txt,.xlsx", "x-ref": "file"}
        ),
        help_text=_("Supported: CSV, TSV, structured TXT and XLSX."),
    )
    pasted_data = forms.CharField(
        required=False,
        label=_("Pasted tabular data"),
        widget=forms.Textarea(
            attrs={"class": "textarea font-mono text-sm", "rows": 10, "spellcheck": "false"}
        ),
    )

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("source_mode")
        source_file = cleaned.get("source_file")
        pasted_data = cleaned.get("pasted_data", "")
        if mode == self.SOURCE_UPLOAD and source_file is None:
            self.add_error("source_file", _("Choose a dataset file to upload."))
        if mode == self.SOURCE_PASTE and not pasted_data.strip():
            self.add_error("pasted_data", _("Paste tabular data before importing."))
        return cleaned


class NewDatasetVersionForm(ImportOptionsMixin, forms.Form):
    source_file = forms.FileField(
        label=_("New source file"),
        widget=forms.ClearableFileInput(
            attrs={"class": "input", "accept": ".csv,.tsv,.txt,.xlsx"}
        ),
    )


class ReprocessDatasetVersionForm(ImportOptionsMixin, forms.Form):
    pass


class DeleteDatasetForm(forms.Form):
    confirmation = forms.CharField(
        label=_("Type the dataset name to confirm"),
        widget=forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
    )

    def __init__(self, *args, dataset_name: str, **kwargs):
        self.dataset_name = dataset_name
        super().__init__(*args, **kwargs)

    def clean_confirmation(self):
        value = self.cleaned_data["confirmation"]
        if value != self.dataset_name:
            raise forms.ValidationError(_("Enter the exact dataset name to confirm deletion."))
        return value
