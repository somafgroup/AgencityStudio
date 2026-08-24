"""Guided forms for System identity and immutable scientific revisions."""

from __future__ import annotations

from django import forms
from django.forms import formset_factory
from django.utils.translation import gettext_lazy as _

from .models import (
    CharacteristicPowerMode,
    MemoryWindowMode,
    ObservableNature,
    ParameterOrigin,
    RevisionDocumentationStatus,
    System,
)

INPUT = {"class": "input"}
TEXTAREA = {"class": "textarea", "rows": 3}
SELECT = {"class": "select"}


class SystemIdentityForm(forms.ModelForm):
    class Meta:
        model = System
        fields = ("name", "description")
        labels = {
            "name": _("System name"),
            "description": _("Organisational description"),
        }
        widgets = {
            "name": forms.TextInput(attrs={**INPUT, "autocomplete": "off"}),
            "description": forms.Textarea(attrs=TEXTAREA),
        }


class SystemRevisionForm(forms.Form):
    documentation_status = forms.ChoiceField(
        choices=RevisionDocumentationStatus.choices,
        initial=RevisionDocumentationStatus.DRAFT,
        label=_("Documentation status"),
        help_text=_("Documented means the required scientific context is complete; it does not mean experimentally validated."),
        widget=forms.Select(attrs=SELECT),
    )
    description = forms.CharField(required=False, label=_("Scientific description"), widget=forms.Textarea(attrs=TEXTAREA))
    domain = forms.CharField(required=False, max_length=160, label=_("Domain"), widget=forms.TextInput(attrs=INPUT))
    system_type = forms.CharField(required=False, max_length=160, label=_("System type"), widget=forms.TextInput(attrs=INPUT))
    mechanism = forms.CharField(required=False, label=_("Physical/scientific mechanism"), widget=forms.Textarea(attrs=TEXTAREA))
    environment = forms.CharField(required=False, max_length=160, label=_("Environment"), widget=forms.TextInput(attrs=INPUT))
    measurement_context = forms.CharField(required=False, label=_("Measurement or simulation context"), widget=forms.Textarea(attrs=TEXTAREA))
    scientific_notes = forms.CharField(required=False, label=_("Scientific notes"), widget=forms.Textarea(attrs=TEXTAREA))
    revision_reason = forms.CharField(required=False, label=_("Reason for this revision"), widget=forms.Textarea(attrs=TEXTAREA))

    a_ref_value_text = forms.CharField(required=False, max_length=80, label=_("A_ref value"), widget=forms.TextInput(attrs={**INPUT, "placeholder": "e.g. 1.2"}))
    a_ref_unit = forms.CharField(required=False, max_length=80, label=_("A_ref unit"), widget=forms.TextInput(attrs={**INPUT, "placeholder": "rad"}))
    a_ref_origin = forms.ChoiceField(required=False, choices=(("", _("Select an origin")), *ParameterOrigin.choices), label=_("A_ref origin"), widget=forms.Select(attrs=SELECT))
    a_ref_origin_detail = forms.CharField(required=False, max_length=255, label=_("A_ref source detail"), widget=forms.TextInput(attrs=INPUT))
    a_ref_justification = forms.CharField(required=False, label=_("A_ref justification"), widget=forms.Textarea(attrs=TEXTAREA))

    tau_value_text = forms.CharField(required=False, max_length=80, label=_("tau value"), widget=forms.TextInput(attrs={**INPUT, "placeholder": "e.g. 0.8"}))
    tau_unit = forms.CharField(required=False, max_length=80, label=_("tau unit"), widget=forms.TextInput(attrs={**INPUT, "placeholder": "s"}))
    tau_origin = forms.ChoiceField(required=False, choices=(("", _("Select an origin")), *ParameterOrigin.choices), label=_("tau origin"), widget=forms.Select(attrs=SELECT))
    tau_origin_detail = forms.CharField(required=False, max_length=255, label=_("tau source detail / mechanism"), widget=forms.TextInput(attrs=INPUT))
    tau_justification = forms.CharField(required=False, label=_("tau justification"), widget=forms.Textarea(attrs=TEXTAREA))

    w_mode = forms.ChoiceField(choices=MemoryWindowMode.choices, initial=MemoryWindowMode.UNSPECIFIED, label=_("Memory window w"), widget=forms.Select(attrs=SELECT))
    w_value_text = forms.CharField(required=False, max_length=80, label=_("w value"), widget=forms.TextInput(attrs=INPUT))
    w_unit = forms.CharField(required=False, max_length=80, label=_("w unit"), widget=forms.TextInput(attrs={**INPUT, "placeholder": "s"}))
    w_origin = forms.ChoiceField(required=False, choices=(("", _("Select an origin")), *ParameterOrigin.choices), label=_("w origin"), widget=forms.Select(attrs=SELECT))
    w_origin_detail = forms.CharField(required=False, max_length=255, label=_("w source detail"), widget=forms.TextInput(attrs=INPUT))
    w_justification = forms.CharField(required=False, label=_("w justification"), widget=forms.Textarea(attrs=TEXTAREA))

    p_c_mode = forms.ChoiceField(choices=CharacteristicPowerMode.choices, initial=CharacteristicPowerMode.FIXED, label=_("P_c mode"), widget=forms.Select(attrs=SELECT))
    p_c_value_text = forms.CharField(required=False, max_length=80, label=_("P_c value"), widget=forms.TextInput(attrs={**INPUT, "placeholder": "e.g. 250"}))
    p_c_unit = forms.CharField(required=False, max_length=80, label=_("P_c unit"), widget=forms.TextInput(attrs={**INPUT, "placeholder": "W"}))
    p_c_origin = forms.ChoiceField(required=False, choices=(("", _("Select an origin")), *ParameterOrigin.choices), label=_("P_c origin"), widget=forms.Select(attrs=SELECT))
    p_c_origin_detail = forms.CharField(required=False, max_length=255, label=_("P_c source detail"), widget=forms.TextInput(attrs=INPUT))
    p_c_justification = forms.CharField(required=False, label=_("P_c justification"), widget=forms.Textarea(attrs=TEXTAREA))


class ObservableInputForm(forms.Form):
    name = forms.CharField(required=False, max_length=180, label=_("Observable name"), widget=forms.TextInput(attrs=INPUT))
    symbol = forms.CharField(required=False, max_length=80, label=_("Symbol"), widget=forms.TextInput(attrs=INPUT))
    description = forms.CharField(required=False, label=_("Description"), widget=forms.Textarea(attrs={"class": "textarea", "rows": 2}))
    unit = forms.CharField(required=False, max_length=80, label=_("Unit"), widget=forms.TextInput(attrs=INPUT))
    observable_kind = forms.CharField(required=False, max_length=120, label=_("Observable kind"), widget=forms.TextInput(attrs=INPUT))
    nature = forms.ChoiceField(required=False, choices=(("", _("Select nature")), *ObservableNature.choices), label=_("Measurement nature"), widget=forms.Select(attrs=SELECT))
    source_description = forms.CharField(required=False, label=_("Measurement / simulation source"), widget=forms.Textarea(attrs={"class": "textarea", "rows": 2}))
    is_primary = forms.BooleanField(required=False, label=_("Primary observable"))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("name") and not cleaned.get("nature"):
            self.add_error("nature", _("Choose how this observable is obtained."))
        return cleaned


class ScientificReferenceInputForm(forms.Form):
    title = forms.CharField(required=False, max_length=255, label=_("Reference title"), widget=forms.TextInput(attrs=INPUT))
    citation = forms.CharField(required=False, label=_("Citation"), widget=forms.Textarea(attrs={"class": "textarea", "rows": 2}))
    doi = forms.CharField(required=False, max_length=255, label=_("DOI"), widget=forms.TextInput(attrs=INPUT))
    url = forms.URLField(
        required=False,
        max_length=500,
        label=_("URL"),
        assume_scheme="https",
        widget=forms.URLInput(attrs=INPUT),
    )
    notes = forms.CharField(required=False, label=_("Notes"), widget=forms.Textarea(attrs={"class": "textarea", "rows": 2}))
    supports_a_ref = forms.BooleanField(required=False, label=_("Supports A_ref"))
    supports_tau = forms.BooleanField(required=False, label=_("Supports tau"))
    supports_w = forms.BooleanField(required=False, label=_("Supports w"))
    supports_p_c = forms.BooleanField(required=False, label=_("Supports P_c"))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("title") and not cleaned.get("citation"):
            cleaned["citation"] = cleaned["title"]
        return cleaned


ObservableFormSet = formset_factory(ObservableInputForm, extra=3, max_num=8, validate_max=True)
ReferenceFormSet = formset_factory(ScientificReferenceInputForm, extra=2, max_num=8, validate_max=True)


class DeleteSystemForm(forms.Form):
    confirmation = forms.CharField(label=_("Type the exact system name"), widget=forms.TextInput(attrs=INPUT))

    def __init__(self, *args, system_name: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.system_name = system_name

    def clean_confirmation(self):
        value = self.cleaned_data["confirmation"]
        if value != self.system_name:
            raise forms.ValidationError(_("Enter the exact system name to confirm deletion."))
        return value
