"""Workspace data model for AgencityStudio."""

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class WorkspaceType(models.TextChoices):
    PERSONAL = "PERSONAL", _("Personal")
    ORGANISATION = "ORGANISATION", _("Organisation")


class WorkspaceRole(models.TextChoices):
    OWNER = "OWNER", _("Owner")
    EDITOR = "EDITOR", _("Editor")
    ANALYST = "ANALYST", _("Analyst")
    VIEWER = "VIEWER", _("Viewer")


class InvitationStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    ACCEPTED = "ACCEPTED", _("Accepted")
    REVOKED = "REVOKED", _("Revoked")
    EXPIRED = "EXPIRED", _("Expired")


class Workspace(models.Model):
    """Logical security and ownership boundary for future scientific objects."""

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    type = models.CharField(max_length=16, choices=WorkspaceType.choices)
    description = models.TextField(blank=True)
    personal_owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="personal_workspace",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(type=WorkspaceType.PERSONAL, personal_owner__isnull=False)
                    | Q(type=WorkspaceType.ORGANISATION, personal_owner__isnull=True)
                ),
                name="workspace_personal_owner_matches_type",
            ),
        ]

    @property
    def is_personal(self) -> bool:
        return self.type == WorkspaceType.PERSONAL

    def __str__(self) -> str:
        return self.name


class WorkspaceMembership(models.Model):
    """A user's explicit role inside one workspace."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workspace_memberships",
    )
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=16, choices=WorkspaceRole.choices)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["workspace_id", "joined_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=("user", "workspace"),
                name="workspace_membership_user_workspace_unique",
            ),
        ]
        indexes = [
            models.Index(fields=("user", "workspace"), name="membership_user_workspace_idx"),
            models.Index(fields=("workspace", "role"), name="membership_workspace_role_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user} · {self.workspace} · {self.role}"


class WorkspaceInvitation(models.Model):
    """Single-use invitation represented externally by a secret token."""

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    email = models.EmailField()
    role = models.CharField(max_length=16, choices=WorkspaceRole.choices)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="workspace_invitations_sent",
    )
    token_digest = models.CharField(max_length=64, unique=True, editable=False)
    status = models.CharField(
        max_length=16,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "email"),
                condition=Q(status=InvitationStatus.PENDING),
                name="workspace_pending_invitation_unique",
            ),
        ]
        indexes = [
            models.Index(fields=("workspace", "status"), name="invitation_workspace_status_idx"),
            models.Index(fields=("email", "status"), name="invitation_email_status_idx"),
        ]

    def save(self, *args, **kwargs):
        self.email = BaseUserManager.normalize_email(self.email).strip().lower()
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()

    def __str__(self) -> str:
        return f"{self.email} → {self.workspace}"
