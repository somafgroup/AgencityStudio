"""Transactional workspace operations and invariants."""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.utils import timezone
from django.utils.text import slugify

from .models import (
    InvitationStatus,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
    WorkspaceRole,
    WorkspaceType,
)
from .permissions import can_manage_members, can_manage_workspace

User = get_user_model()


def _unique_workspace_slug(name: str, *, personal: bool = False) -> str:
    base = slugify(name)[:140] or ("personal" if personal else "workspace")
    candidate = base
    for _ in range(10):
        if not Workspace.objects.filter(slug=candidate).exists():
            return candidate
        candidate = f"{base[:165]}-{secrets.token_hex(3)}"
    raise ValidationError("Could not allocate a unique workspace slug.")


@transaction.atomic
def ensure_personal_workspace(user) -> Workspace:
    """Ensure a user has exactly one private personal workspace and Owner membership."""
    try:
        workspace = Workspace.objects.select_for_update().get(personal_owner=user)
    except Workspace.DoesNotExist:
        label = user.display_name.strip() or user.email.split("@", maxsplit=1)[0]
        workspace = Workspace.objects.create(
            name=f"{label}'s workspace",
            slug=_unique_workspace_slug(f"{label}-personal", personal=True),
            type=WorkspaceType.PERSONAL,
            personal_owner=user,
        )
    WorkspaceMembership.objects.update_or_create(
        user=user,
        workspace=workspace,
        defaults={"role": WorkspaceRole.OWNER},
    )
    return workspace


@transaction.atomic
def create_organisation_workspace(*, owner, name: str, description: str = "") -> Workspace:
    """Create an organisation workspace and its first Owner atomically."""
    clean_name = name.strip()
    if not clean_name:
        raise ValidationError("Workspace name is required.")
    workspace = Workspace.objects.create(
        name=clean_name,
        slug=_unique_workspace_slug(clean_name),
        type=WorkspaceType.ORGANISATION,
        description=description.strip(),
    )
    WorkspaceMembership.objects.create(
        user=owner,
        workspace=workspace,
        role=WorkspaceRole.OWNER,
    )
    return workspace


def workspace_memberships_for(user):
    """Return workspace memberships without N+1 workspace queries."""
    return (
        WorkspaceMembership.objects.filter(user=user)
        .select_related("workspace")
        .order_by("workspace__type", "workspace__name")
    )


def get_workspace_membership_or_404(*, user, slug: str) -> WorkspaceMembership:
    """Hide private workspace existence from non-members by returning 404."""
    if not getattr(user, "is_authenticated", False):
        raise Http404
    try:
        return WorkspaceMembership.objects.select_related("workspace", "user").get(
            user=user,
            workspace__slug=slug,
        )
    except WorkspaceMembership.DoesNotExist as exc:
        raise Http404 from exc


@transaction.atomic
def update_workspace(*, actor, workspace: Workspace, name: str, description: str) -> Workspace:
    if not can_manage_workspace(actor, workspace):
        raise PermissionDenied
    clean_name = name.strip()
    if not clean_name:
        raise ValidationError("Workspace name is required.")
    locked = Workspace.objects.select_for_update().get(pk=workspace.pk)
    locked.name = clean_name
    locked.description = description.strip()
    locked.save(update_fields=("name", "description", "updated_at"))
    return locked


def _owner_count_locked(workspace: Workspace) -> int:
    owner_ids = list(
        WorkspaceMembership.objects.select_for_update()
        .filter(workspace=workspace, role=WorkspaceRole.OWNER)
        .values_list("pk", flat=True)
    )
    return len(owner_ids)


@transaction.atomic
def change_member_role(*, actor, membership: WorkspaceMembership, role: str) -> WorkspaceMembership:
    """Change a role while preventing removal of the final organisation Owner."""
    if not can_manage_members(actor, membership.workspace):
        raise PermissionDenied
    if membership.workspace.is_personal:
        raise ValidationError("Personal workspace ownership cannot be changed.")
    if role not in WorkspaceRole.values:
        raise ValidationError("Unknown workspace role.")

    locked = WorkspaceMembership.objects.select_for_update().select_related("workspace").get(
        pk=membership.pk
    )
    if (
        locked.role == WorkspaceRole.OWNER
        and role != WorkspaceRole.OWNER
        and _owner_count_locked(locked.workspace) <= 1
    ):
        raise ValidationError("A workspace must keep at least one Owner.")
    locked.role = role
    locked.save(update_fields=("role",))
    return locked


@transaction.atomic
def remove_member(*, actor, membership: WorkspaceMembership) -> None:
    """Remove a member while protecting personal workspaces and the final Owner."""
    if membership.workspace.is_personal:
        raise ValidationError("The personal workspace membership cannot be removed.")
    if actor != membership.user and not can_manage_members(actor, membership.workspace):
        raise PermissionDenied
    if actor == membership.user and not getattr(actor, "is_authenticated", False):
        raise PermissionDenied

    locked = WorkspaceMembership.objects.select_for_update().select_related("workspace").get(
        pk=membership.pk
    )
    if locked.role == WorkspaceRole.OWNER and _owner_count_locked(locked.workspace) <= 1:
        raise ValidationError("The last Owner cannot leave or be removed.")
    locked.delete()


@transaction.atomic
def delete_organisation_workspace(*, actor, workspace: Workspace) -> None:
    if workspace.is_personal:
        raise ValidationError("Personal workspaces cannot be deleted.")
    if not can_manage_workspace(actor, workspace):
        raise PermissionDenied
    Workspace.objects.select_for_update().get(pk=workspace.pk).delete()


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@transaction.atomic
def invite_member(*, actor, workspace: Workspace, email: str, role: str):
    """Create a single-use invitation and return it with its raw token exactly once."""
    if not can_manage_members(actor, workspace):
        raise PermissionDenied
    if workspace.is_personal:
        raise ValidationError("Personal workspaces cannot be shared by membership.")
    if role not in WorkspaceRole.values:
        raise ValidationError("Unknown workspace role.")

    normalized_email = User.objects.normalize_studio_email(email)
    existing_user = User.objects.filter(email__iexact=normalized_email).first()
    if existing_user and WorkspaceMembership.objects.filter(
        user=existing_user,
        workspace=workspace,
    ).exists():
        raise ValidationError("This person is already a member of the workspace.")

    pending = WorkspaceInvitation.objects.filter(
        workspace=workspace,
        email=normalized_email,
        status=InvitationStatus.PENDING,
    ).first()
    if pending:
        if pending.is_expired:
            pending.status = InvitationStatus.EXPIRED
            pending.save(update_fields=("status",))
        else:
            raise ValidationError("A pending invitation already exists for this email address.")

    token = secrets.token_urlsafe(32)
    invitation = WorkspaceInvitation.objects.create(
        workspace=workspace,
        email=normalized_email,
        role=role,
        invited_by=actor,
        token_digest=_token_digest(token),
        expires_at=timezone.now()
        + timedelta(seconds=getattr(settings, "WORKSPACE_INVITATION_TTL", 604800)),
    )
    return invitation, token


def resolve_invitation(token: str) -> WorkspaceInvitation | None:
    """Resolve a raw invitation token without storing or logging the secret value."""
    digest = _token_digest(token)
    invitation = (
        WorkspaceInvitation.objects.select_related("workspace", "invited_by")
        .filter(token_digest=digest)
        .first()
    )
    if invitation is None:
        return None
    if invitation.status == InvitationStatus.PENDING and invitation.is_expired:
        invitation.status = InvitationStatus.EXPIRED
        invitation.save(update_fields=("status",))
    return invitation


def accept_invitation(*, user, token: str) -> WorkspaceMembership:
    """Accept a valid invitation atomically and prevent token reuse."""
    digest = _token_digest(token)
    expired = False
    membership = None

    with transaction.atomic():
        try:
            invitation = (
                WorkspaceInvitation.objects.select_for_update()
                .select_related("workspace")
                .get(token_digest=digest)
            )
        except WorkspaceInvitation.DoesNotExist as exc:
            raise ValidationError("This invitation is invalid.") from exc

        if invitation.status != InvitationStatus.PENDING:
            raise ValidationError("This invitation is no longer available.")
        if invitation.is_expired:
            invitation.status = InvitationStatus.EXPIRED
            invitation.save(update_fields=("status",))
            expired = True
        else:
            if user.email.lower() != invitation.email.lower():
                raise PermissionDenied("This invitation belongs to a different email address.")

            try:
                membership, _ = WorkspaceMembership.objects.get_or_create(
                    user=user,
                    workspace=invitation.workspace,
                    defaults={"role": invitation.role},
                )
            except IntegrityError:
                membership = WorkspaceMembership.objects.get(
                    user=user,
                    workspace=invitation.workspace,
                )

            invitation.status = InvitationStatus.ACCEPTED
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=("status", "accepted_at"))

    if expired:
        raise ValidationError("This invitation has expired.")
    if membership is None:
        raise ValidationError("This invitation could not be accepted.")
    return membership


@transaction.atomic
def revoke_invitation(*, actor, invitation: WorkspaceInvitation) -> WorkspaceInvitation:
    if not can_manage_members(actor, invitation.workspace):
        raise PermissionDenied
    locked = WorkspaceInvitation.objects.select_for_update().get(pk=invitation.pk)
    if locked.status != InvitationStatus.PENDING:
        raise ValidationError("Only pending invitations can be revoked.")
    locked.status = InvitationStatus.REVOKED
    locked.save(update_fields=("status",))
    return locked
