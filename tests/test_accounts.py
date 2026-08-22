from urllib.parse import urlparse

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from workspaces.models import WorkspaceRole, WorkspaceType


User = get_user_model()
PASSWORD = "Scientific-Plan2-Password!42"
NEW_PASSWORD = "Scientific-Plan2-NewPassword!84"


@pytest.mark.django_db
def test_signup_creates_email_identity_personal_workspace_and_session(client):
    response = client.post(
        reverse("accounts:signup"),
        {
            "email": "Researcher@Example.COM",
            "display_name": "Researcher",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("dashboard")
    user = User.objects.get()
    assert user.email == "researcher@example.com"
    assert user.personal_workspace.type == WorkspaceType.PERSONAL
    membership = user.workspace_memberships.get(workspace=user.personal_workspace)
    assert membership.role == WorkspaceRole.OWNER
    assert client.get(reverse("dashboard")).status_code == 200


@pytest.mark.django_db
def test_login_logout_and_email_identifier(client):
    User.objects.create_user(email="member@example.com", password=PASSWORD)

    login_response = client.post(
        reverse("accounts:login"),
        {"username": "member@example.com", "password": PASSWORD},
    )
    assert login_response.status_code == 302
    assert login_response.url == reverse("dashboard")

    logout_response = client.post(reverse("accounts:logout"))
    assert logout_response.status_code == 302
    assert client.get(reverse("dashboard")).status_code == 302


@pytest.mark.django_db
@override_settings(SIGNUP_MODE="invitation_only")
def test_public_signup_can_be_disabled_without_disabling_local_login(client):
    response = client.get(reverse("accounts:signup"))
    assert response.status_code == 403


@pytest.mark.django_db
def test_password_reset_changes_password_through_emailed_link(client):
    user = User.objects.create_user(email="reset@example.com", password=PASSWORD)

    response = client.post(reverse("accounts:password-reset"), {"email": user.email})
    assert response.status_code == 302
    assert len(mail.outbox) == 1

    reset_url = next(
        line for line in mail.outbox[0].body.splitlines() if line.startswith("http://testserver/")
    )
    reset_path = urlparse(reset_url).path
    response = client.get(reset_path)
    assert response.status_code == 302

    response = client.post(
        response.url,
        {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
    )
    assert response.status_code == 302

    user.refresh_from_db()
    assert not user.check_password(PASSWORD)
    assert user.check_password(NEW_PASSWORD)


@pytest.mark.django_db
def test_profile_and_preferences_persist(client):
    user = User.objects.create_user(email="profile@example.com", password=PASSWORD)
    client.force_login(user)

    profile_response = client.post(
        reverse("accounts:profile"),
        {"display_name": "A. Researcher", "email": "NewProfile@example.com"},
    )
    assert profile_response.status_code == 302

    preference_response = client.post(
        reverse("accounts:preferences"),
        {"theme": "dark", "locale": "fr", "timezone": "Europe/Paris"},
    )
    assert preference_response.status_code == 302

    user.refresh_from_db()
    assert user.display_name == "A. Researcher"
    assert user.email == "newprofile@example.com"
    assert user.theme == "dark"
    assert user.locale == "fr"
    assert user.timezone == "Europe/Paris"
