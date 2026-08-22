"""Forms for workspace creation, membership and invitation management."""

from django import forms
from django.utils.translation import gettext_lazy as _

from accounts.forms import StyledFormMixin

from .models import WorkspaceRole


class OrganisationWorkspaceForm(StyledFormMixin, forms.Form):
    name = forms.CharField(label=_("Workspace name"), max_length=160)
    description = forms.CharField(
        label=_("Description"),
        required=False,
        widget=forms.Textarea,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class WorkspaceSettingsForm(OrganisationWorkspaceForm):
    pass


class InvitationForm(StyledFormMixin, forms.Form):
    email = forms.EmailField(label=_("Email"), widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    role = forms.ChoiceField(label=_("Role"), choices=WorkspaceRole.choices)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class RoleChangeForm(StyledFormMixin, forms.Form):
    role = forms.ChoiceField(label=_("Role"), choices=WorkspaceRole.choices)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class DeleteWorkspaceForm(StyledFormMixin, forms.Form):
    confirm_name = forms.CharField(label=_("Type the workspace name to confirm"), max_length=160)

    def __init__(self, *args, workspace_name: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace_name = workspace_name
        self._style_fields()

    def clean_confirm_name(self):
        value = self.cleaned_data["confirm_name"].strip()
        if value != self.workspace_name:
            raise forms.ValidationError(_("The workspace name does not match."))
        return value
