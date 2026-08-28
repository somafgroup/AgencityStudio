"""Forms for explicit N-dimensional observable-field source uploads."""

from pathlib import Path

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class FieldDatasetImportForm(forms.Form):
    name = forms.CharField(max_length=180, label=_("Dataset name"))
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label=_("Description"),
    )
    source_file = forms.FileField(
        label=_("NPZ field source"),
        widget=forms.ClearableFileInput(attrs={"accept": ".npz"}),
        help_text=_(
            "Upload exact NumPy arrays. Object/pickle arrays are rejected and Studio does not reshape field data."
        ),
    )

    def clean_source_file(self):
        uploaded = self.cleaned_data["source_file"]
        if Path(uploaded.name or "").suffix.lower() != ".npz":
            raise ValidationError(_("Observable field sources must use the .npz format."))
        limit = min(
            int(settings.DATASET_MAX_UPLOAD_BYTES),
            int(getattr(settings, "FIELD_MAX_UPLOAD_BYTES", settings.DATASET_MAX_UPLOAD_BYTES)),
        )
        if getattr(uploaded, "size", 0) > limit:
            raise ValidationError(_("The field source exceeds the configured upload size limit."))
        return uploaded
