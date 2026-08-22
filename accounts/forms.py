"""Forms for local account authentication and preferences."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.utils.translation import gettext_lazy as _

from .models import User, UserManager


class StyledFormMixin:
    """Apply the shared Plan 1 form primitives to Django forms."""

    def _style_fields(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                continue
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "select")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "textarea")
            else:
                widget.attrs.setdefault("class", "input")


class EmailAuthenticationForm(StyledFormMixin, AuthenticationForm):
    username = forms.EmailField(label=_("Email"), widget=forms.EmailInput(autocomplete="email"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password"].widget.attrs["autocomplete"] = "current-password"
        self._style_fields()


class SignupForm(StyledFormMixin, UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "display_name")
        widgets = {
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "display_name": forms.TextInput(attrs={"autocomplete": "name"}),
        }

    def __init__(self, *args, invited_email: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.invited_email = invited_email
        self.fields["display_name"].required = False
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"
        if invited_email:
            self.fields["email"].initial = invited_email
            self.fields["email"].disabled = True
        self._style_fields()

    def clean_email(self):
        email = UserManager.normalize_studio_email(self.cleaned_data["email"])
        if self.invited_email and email != UserManager.normalize_studio_email(self.invited_email):
            raise forms.ValidationError(_("Use the email address that received the invitation."))
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("An account already exists for this email address."))
        return email

    def save(self, commit=True):
        if not commit:
            return super().save(commit=False)
        return User.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            display_name=self.cleaned_data.get("display_name", ""),
        )


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("display_name", "email")
        widgets = {
            "display_name": forms.TextInput(attrs={"autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_email(self):
        email = UserManager.normalize_studio_email(self.cleaned_data["email"])
        duplicate = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError(_("Another account already uses this email address."))
        return email


class PreferencesForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("theme", "locale", "timezone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["timezone"].help_text = _("Use an IANA timezone such as Europe/Paris or UTC.")
        self._style_fields()

    def clean_timezone(self):
        value = self.cleaned_data["timezone"].strip()
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise forms.ValidationError(_("Enter a valid IANA timezone.")) from exc
        return value


class StyledPasswordResetForm(StyledFormMixin, PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class StyledSetPasswordForm(StyledFormMixin, SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class ThemePreferenceForm(forms.Form):
    theme = forms.ChoiceField(choices=User.Theme.choices)
