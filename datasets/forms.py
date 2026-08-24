"""Forms for Dataset import, metadata, and explicit preparation recipes."""

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Dataset
from .preparation import OPERATION_LABELS


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


class PreparationCreateForm(forms.Form):
    name = forms.CharField(
        max_length=180,
        label=_("Preparation name"),
        widget=forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
    )
    description = forms.CharField(
        required=False,
        label=_("Description"),
        widget=forms.Textarea(attrs={"class": "textarea", "rows": 3}),
    )


class PreparationStepForm(forms.Form):
    """One controlled transformation step; no user code or arbitrary expression is accepted."""

    operation = forms.ChoiceField(
        label=_("Transformation"),
        choices=[(key, label) for key, label in OPERATION_LABELS.items()],
        widget=forms.Select(attrs={"class": "select"}),
    )
    time_column = forms.ChoiceField(required=False, label=_("Time column"), widget=forms.Select(attrs={"class": "select"}))
    columns = forms.MultipleChoiceField(required=False, label=_("Target columns"), widget=forms.SelectMultiple(attrs={"class": "select", "size": 5}))
    coordinate_column = forms.ChoiceField(required=False, label=_("Interpolation coordinate"), widget=forms.Select(attrs={"class": "select"}))
    start = forms.CharField(required=False, label=_("Start"), widget=forms.TextInput(attrs={"class": "input"}))
    end = forms.CharField(required=False, label=_("End"), widget=forms.TextInput(attrs={"class": "input"}))
    start_row = forms.IntegerField(required=False, min_value=1, label=_("Start row"), widget=forms.NumberInput(attrs={"class": "input"}))
    end_row = forms.IntegerField(required=False, min_value=1, label=_("End row"), widget=forms.NumberInput(attrs={"class": "input"}))
    excluded_rows = forms.CharField(required=False, label=_("Rows to exclude"), help_text=_("Comma-separated one-based row numbers."), widget=forms.TextInput(attrs={"class": "input", "placeholder": "417, 418"}))
    missing_action = forms.ChoiceField(
        required=False,
        label=_("Missing-value treatment"),
        choices=(("remove_rows", _("Remove affected rows")), ("interpolate_linear", _("Linear interpolation"))),
        widget=forms.Select(attrs={"class": "select"}),
    )
    target_dt = forms.FloatField(required=False, min_value=0, label=_("Target sampling interval dt"), widget=forms.NumberInput(attrs={"class": "input", "step": "any"}), help_text=_("This is sampling interval dt; it is not tau and not CRM window w."))
    dt_unit = forms.CharField(required=False, max_length=80, label=_("dt unit"), widget=forms.TextInput(attrs={"class": "input", "placeholder": "s"}))
    window_samples = forms.IntegerField(required=False, min_value=3, label=_("Moving-average window (samples)"), widget=forms.NumberInput(attrs={"class": "input", "step": 2}))
    target_unit = forms.CharField(required=False, max_length=80, label=_("Target unit"), widget=forms.TextInput(attrs={"class": "input", "placeholder": "m/s"}))

    def __init__(self, *args, version, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [(str(column.position), column.display_name) for column in version.columns.order_by("position")]
        optional = [("", _("Select a column")), *choices]
        self.fields["time_column"].choices = optional
        self.fields["coordinate_column"].choices = optional
        self.fields["columns"].choices = choices

    def _require(self, name):
        value = self.cleaned_data.get(name)
        if value is None or value == "" or value == []:
            self.add_error(name, _("This value is required for the selected transformation."))
        return value

    def clean(self):
        cleaned = super().clean()
        operation = cleaned.get("operation")
        if not operation:
            return cleaned
        requirements = {
            "time_crop": ("time_column", "start", "end"),
            "row_range": ("start_row", "end_row"),
            "exclude_rows": ("excluded_rows",),
            "missing_values": ("columns", "missing_action"),
            "resample": ("time_column", "columns", "target_dt"),
            "moving_average": ("columns", "window_samples"),
            "unit_conversion": ("columns", "target_unit"),
            "select_columns": ("columns",),
            "sort_time": ("time_column",),
        }
        for name in requirements.get(operation, ()):
            self._require(name)
        if operation == "missing_values" and cleaned.get("missing_action") == "interpolate_linear":
            self._require("coordinate_column")
        if (
            operation == "moving_average"
            and cleaned.get("window_samples")
            and cleaned["window_samples"] % 2 == 0
        ):
            self.add_error("window_samples", _("Use an odd number of samples."))
        if operation == "resample" and cleaned.get("target_dt") == 0:
            self.add_error("target_dt", _("Target dt must be greater than zero."))
        return cleaned

    def step(self) -> dict:
        operation = self.cleaned_data["operation"]
        columns = [int(value) for value in self.cleaned_data.get("columns") or []]
        parameters: dict = {}
        if operation == "time_crop":
            parameters = {"time_column": int(self.cleaned_data["time_column"]), "start": self.cleaned_data["start"], "end": self.cleaned_data["end"]}
        elif operation == "row_range":
            parameters = {"start_row": self.cleaned_data["start_row"], "end_row": self.cleaned_data["end_row"]}
        elif operation == "exclude_rows":
            try:
                rows = [int(value.strip()) for value in self.cleaned_data["excluded_rows"].split(",") if value.strip()]
            except ValueError as exc:
                raise forms.ValidationError(_("Rows to exclude must be comma-separated integers.")) from exc
            parameters = {"rows": rows}
        elif operation == "missing_values":
            parameters = {"columns": columns, "action": self.cleaned_data["missing_action"]}
            if self.cleaned_data["missing_action"] == "interpolate_linear":
                parameters["coordinate_column"] = int(self.cleaned_data["coordinate_column"])
        elif operation == "resample":
            parameters = {"time_column": int(self.cleaned_data["time_column"]), "columns": columns, "target_dt": self.cleaned_data["target_dt"], "dt_unit": self.cleaned_data.get("dt_unit", "").strip()}
        elif operation == "moving_average":
            parameters = {"columns": columns, "window_samples": self.cleaned_data["window_samples"]}
        elif operation == "unit_conversion":
            if len(columns) != 1:
                raise forms.ValidationError(_("Unit conversion accepts exactly one column per step."))
            parameters = {"column": columns[0], "target_unit": self.cleaned_data["target_unit"].strip()}
        elif operation == "select_columns":
            parameters = {"columns": columns}
        elif operation == "sort_time":
            parameters = {"time_column": int(self.cleaned_data["time_column"])}
        return {"operation": operation, "parameters": parameters}


class DeletePreparationForm(forms.Form):
    confirmation = forms.BooleanField(label=_("I understand that the prepared result will be deleted."))
