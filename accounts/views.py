"""Local account workflows built on Django's session authentication."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext as _

from workspaces.models import InvitationStatus
from workspaces.services import accept_invitation, resolve_invitation

from .forms import (
    EmailAuthenticationForm,
    PreferencesForm,
    ProfileForm,
    SignupForm,
    ThemePreferenceForm,
)


class StudioLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


class StudioLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")


class StudioPasswordChangeView(PasswordChangeView):
    template_name = "registration/password_change_form.html"
    success_url = reverse_lazy("accounts:password-change-done")


class StudioPasswordChangeDoneView(PasswordChangeDoneView):
    template_name = "registration/password_change_done.html"


class StudioPasswordResetView(PasswordResetView):
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.txt"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password-reset-done")


class StudioPasswordResetDoneView(PasswordResetDoneView):
    template_name = "registration/password_reset_done.html"


class StudioPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "registration/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password-reset-complete")


class StudioPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "registration/password_reset_complete.html"


def _signup_mode_allows_public() -> bool:
    return getattr(settings, "SIGNUP_MODE", "public") == "public"


def signup(request):
    """Create a local account when public registration is enabled."""
    if request.user.is_authenticated:
        return redirect("dashboard")
    if not _signup_mode_allows_public():
        return render(
            request,
            "registration/signup_unavailable.html",
            {"page_title": _("Sign up unavailable")},
            status=403,
        )

    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, _("Your account is ready."))
        return redirect("dashboard")
    return render(
        request,
        "registration/signup.html",
        {"form": form, "page_title": _("Create account")},
    )


def invited_signup(request, token: str):
    """Create the invited identity and atomically accept the matching invitation."""
    invitation = resolve_invitation(token)
    if invitation is None:
        raise Http404
    if invitation.status != InvitationStatus.PENDING:
        return render(
            request,
            "registration/signup_unavailable.html",
            {"page_title": _("Invitation unavailable")},
            status=410,
        )
    if request.user.is_authenticated:
        return redirect("workspaces:accept-invitation", token=token)

    form = SignupForm(request.POST or None, invited_email=invitation.email)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        try:
            membership = accept_invitation(user=user, token=token)
        except (PermissionDenied, ValidationError):
            messages.error(request, _("The account was created, but the invitation is unavailable."))
            return redirect("dashboard")
        request.session["current_workspace_slug"] = membership.workspace.slug
        messages.success(request, _("Account created and invitation accepted."))
        return redirect("workspaces:overview", slug=membership.workspace.slug)

    return render(
        request,
        "registration/signup.html",
        {
            "form": form,
            "invitation": invitation,
            "page_title": _("Join workspace"),
        },
    )


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Profile updated."))
        return redirect("accounts:profile")
    return render(
        request,
        "accounts/profile.html",
        {"form": form, "page_title": _("Profile"), "active_nav": "account"},
    )


@login_required
def preferences(request):
    form = PreferencesForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Preferences updated."))
        return redirect("accounts:preferences")
    return render(
        request,
        "accounts/preferences.html",
        {"form": form, "page_title": _("Preferences"), "active_nav": "account"},
    )


@login_required
def theme_preference(request):
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed."}, status=405)
    form = ThemePreferenceForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"detail": "Invalid theme."}, status=400)
    request.user.theme = form.cleaned_data["theme"]
    request.user.save(update_fields=("theme",))
    return JsonResponse({"theme": request.user.theme})
