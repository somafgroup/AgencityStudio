"""Forms for Project metadata and destructive confirmation."""

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Project


class ProjectForm(forms.ModelForm):
    tags = forms.CharField(
        required=False,
        label=_("Tags"),
        help_text=_("Comma-separated organisational tags."),
        widget=forms.TextInput(attrs={"placeholder": _("mechanics, vibration")}),
    )

    class Meta:
        model = Project
        fields = ("name", "description", "domain", "tags", "notes")
        widgets = {
            "name": forms.TextInput(attrs={"autocomplete": "off"}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "domain": forms.TextInput(
                attrs={"placeholder": _("mechanics, robotics, biology…")}
            ),
            "notes": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and not self.is_bound:
            self.initial["tags"] = ", ".join(self.instance.tags or [])
        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("class", "textarea")
            else:
                field.widget.attrs.setdefault("class", "input")

    def clean_tags(self):
        raw = self.cleaned_data.get("tags", "")
        tags = []
        seen = set()
        for value in raw.split(","):
            tag = " ".join(value.strip().split())[:48]
            key = tag.casefold()
            if tag and key not in seen:
                tags.append(tag)
                seen.add(key)
        return tags[:20]


class DeleteProjectForm(forms.Form):
    confirm_name = forms.CharField(label=_("Project name"))

    def __init__(self, *args, project_name: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.project_name = project_name
        self.fields["confirm_name"].widget.attrs.update({"class": "input", "autocomplete": "off"})

    def clean_confirm_name(self):
        value = self.cleaned_data["confirm_name"]
        if value != self.project_name:
            raise forms.ValidationError(_("Enter the exact project name to confirm deletion."))
        return value
