from datetime import timedelta
from smtplib import SMTPException

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from workspaces.models import InvitationStatus, WorkspaceMembership, WorkspaceRole
from workspaces.permissions import can_edit_workspace, can_manage_members, can_view_workspace
from workspaces.services import (
    accept_invitation,
    change_member_role,
    create_organisation_workspace,
    invite_member,
    remove_member,
    revoke_invitation,
)

User = get_user_model()
PASSWORD = "Scientific-Plan2-Password!42"


def make_user(email: str, **extra):
    return User.objects.create_user(email=email, password=PASSWORD, **extra)


@pytest.mark.django_db
def test_workspace_role_policy_is_explicit_and_staff_does_not_bypass_membership():
    owner = make_user("owner@example.com")
    editor = make_user("editor@example.com")
    analyst = make_user("analyst@example.com")
    viewer = make_user("viewer@example.com")
    staff = make_user("staff@example.com", is_staff=True)
    workspace = create_organisation_workspace(owner=owner, name="Biomechanics Lab")
    WorkspaceMembership.objects.create(user=editor, workspace=workspace, role=WorkspaceRole.EDITOR)
    WorkspaceMembership.objects.create(user=analyst, workspace=workspace, role=WorkspaceRole.ANALYST)
    WorkspaceMembership.objects.create(user=viewer, workspace=workspace, role=WorkspaceRole.VIEWER)

    assert can_manage_members(owner, workspace)
    assert can_edit_workspace(editor, workspace)
    assert can_view_workspace(analyst, workspace)
    assert can_view_workspace(viewer, workspace)
    assert not can_edit_workspace(analyst, workspace)
    assert not can_edit_workspace(viewer, workspace)
    assert not can_manage_members(editor, workspace)
    assert not can_view_workspace(staff, workspace)


@pytest.mark.django_db
def test_organisation_creation_endpoint_creates_owner_membership(client):
    owner = make_user("owner@example.com")
    client.force_login(owner)

    response = client.post(
        reverse("workspaces:create"),
        {"name": "Systems Laboratory", "description": "Team workspace"},
    )

    assert response.status_code == 302
    membership = WorkspaceMembership.objects.get(
        user=owner,
        workspace__name="Systems Laboratory",
    )
    assert membership.role == WorkspaceRole.OWNER
    assert response.url == reverse("workspaces:overview", args=[membership.workspace.slug])


@pytest.mark.django_db
def test_private_workspace_url_returns_404_to_non_member_even_if_staff(client):
    owner = make_user("owner@example.com")
    outsider = make_user("outsider@example.com", is_staff=True)
    workspace = create_organisation_workspace(owner=owner, name="Private Laboratory")
    client.force_login(outsider)

    response = client.get(reverse("workspaces:overview", args=[workspace.slug]))

    assert response.status_code == 404
    assert workspace.name.encode() not in response.content


@pytest.mark.django_db
def test_viewer_can_read_members_but_cannot_manage_them(client):
    owner = make_user("owner@example.com")
    viewer = make_user("viewer@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Shared Lab")
    WorkspaceMembership.objects.create(user=viewer, workspace=workspace, role=WorkspaceRole.VIEWER)
    client.force_login(viewer)

    assert client.get(reverse("workspaces:members", args=[workspace.slug])).status_code == 200
    assert client.get(reverse("workspaces:invite", args=[workspace.slug])).status_code == 403


@pytest.mark.django_db
def test_owner_role_change_and_removal_endpoints_use_central_invariants(client):
    owner = make_user("owner@example.com")
    member = make_user("member@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Role Lab")
    target = WorkspaceMembership.objects.create(
        user=member,
        workspace=workspace,
        role=WorkspaceRole.VIEWER,
    )
    client.force_login(owner)

    response = client.post(
        reverse("workspaces:change-role", args=[workspace.slug, target.pk]),
        {"role": WorkspaceRole.ANALYST},
    )
    assert response.status_code == 302
    target.refresh_from_db()
    assert target.role == WorkspaceRole.ANALYST

    response = client.post(reverse("workspaces:remove-member", args=[workspace.slug, target.pk]))
    assert response.status_code == 302
    assert not WorkspaceMembership.objects.filter(pk=target.pk).exists()


@pytest.mark.django_db
def test_last_owner_cannot_be_demoted_removed_or_leave():
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Owner Lab")
    membership = WorkspaceMembership.objects.get(user=owner, workspace=workspace)

    with pytest.raises(ValidationError, match="at least one Owner"):
        change_member_role(actor=owner, membership=membership, role=WorkspaceRole.EDITOR)
    with pytest.raises(ValidationError, match="last Owner"):
        remove_member(actor=owner, membership=membership)

    second_owner = make_user("second-owner@example.com")
    second_membership = WorkspaceMembership.objects.create(
        user=second_owner,
        workspace=workspace,
        role=WorkspaceRole.OWNER,
    )
    change_member_role(actor=owner, membership=second_membership, role=WorkspaceRole.EDITOR)
    second_membership.refresh_from_db()
    assert second_membership.role == WorkspaceRole.EDITOR


@pytest.mark.django_db
def test_invitation_token_is_hashed_single_use_and_email_bound():
    owner = make_user("owner@example.com")
    invited = make_user("invited@example.com")
    wrong_user = make_user("wrong@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Invitation Lab")

    invitation, token = invite_member(
        actor=owner,
        workspace=workspace,
        email="Invited@Example.COM",
        role=WorkspaceRole.ANALYST,
    )

    assert invitation.email == "invited@example.com"
    assert invitation.token_digest != token
    assert token not in invitation.token_digest
    with pytest.raises(PermissionDenied):
        accept_invitation(user=wrong_user, token=token)

    membership = accept_invitation(user=invited, token=token)
    invitation.refresh_from_db()
    assert membership.role == WorkspaceRole.ANALYST
    assert invitation.status == InvitationStatus.ACCEPTED
    with pytest.raises(ValidationError, match="no longer available"):
        accept_invitation(user=invited, token=token)
    assert WorkspaceMembership.objects.filter(user=invited, workspace=workspace).count() == 1


@pytest.mark.django_db
def test_expired_and_revoked_invitations_cannot_be_accepted():
    owner = make_user("owner@example.com")
    invited = make_user("invited@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Expiry Lab")

    expired, expired_token = invite_member(
        actor=owner,
        workspace=workspace,
        email=invited.email,
        role=WorkspaceRole.VIEWER,
    )
    expired.expires_at = timezone.now() - timedelta(seconds=1)
    expired.save(update_fields=("expires_at",))
    with pytest.raises(ValidationError, match="expired"):
        accept_invitation(user=invited, token=expired_token)
    expired.refresh_from_db()
    assert expired.status == InvitationStatus.EXPIRED

    revoked, revoked_token = invite_member(
        actor=owner,
        workspace=workspace,
        email=invited.email,
        role=WorkspaceRole.VIEWER,
    )
    revoke_invitation(actor=owner, invitation=revoked)
    with pytest.raises(ValidationError, match="no longer available"):
        accept_invitation(user=invited, token=revoked_token)


@pytest.mark.django_db
def test_email_delivery_failure_keeps_invitation_valid(client, monkeypatch):
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Mail Lab")
    client.force_login(owner)

    def fail_delivery(*args, **kwargs):
        raise SMTPException("delivery unavailable")

    monkeypatch.setattr("workspaces.views._send_invitation_email", fail_delivery)
    response = client.post(
        reverse("workspaces:invite", args=[workspace.slug]),
        {"email": "recipient@example.com", "role": WorkspaceRole.VIEWER},
    )

    assert response.status_code == 302
    invitation = workspace.invitations.get(email="recipient@example.com")
    assert invitation.status == InvitationStatus.PENDING


@pytest.mark.django_db
def test_personal_workspace_cannot_be_shared_by_membership_invitation():
    user = make_user("personal@example.com")

    with pytest.raises(ValidationError, match="cannot be shared"):
        invite_member(
            actor=user,
            workspace=user.personal_workspace,
            email="other@example.com",
            role=WorkspaceRole.VIEWER,
        )
