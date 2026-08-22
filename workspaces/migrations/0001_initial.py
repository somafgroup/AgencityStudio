import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Workspace",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=160)),
                ("slug", models.SlugField(max_length=180, unique=True)),
                (
                    "type",
                    models.CharField(
                        choices=[("PERSONAL", "Personal"), ("ORGANISATION", "Organisation")],
                        max_length=16,
                    ),
                ),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "personal_owner",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="personal_workspace",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.CreateModel(
            name="WorkspaceMembership",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("OWNER", "Owner"),
                            ("EDITOR", "Editor"),
                            ("ANALYST", "Analyst"),
                            ("VIEWER", "Viewer"),
                        ],
                        max_length=16,
                    ),
                ),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workspace_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="workspaces.workspace",
                    ),
                ),
            ],
            options={"ordering": ["workspace_id", "joined_at", "id"]},
        ),
        migrations.CreateModel(
            name="WorkspaceInvitation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("email", models.EmailField(max_length=254)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("OWNER", "Owner"),
                            ("EDITOR", "Editor"),
                            ("ANALYST", "Analyst"),
                            ("VIEWER", "Viewer"),
                        ],
                        max_length=16,
                    ),
                ),
                ("token_digest", models.CharField(editable=False, max_length=64, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("ACCEPTED", "Accepted"),
                            ("REVOKED", "Revoked"),
                            ("EXPIRED", "Expired"),
                        ],
                        default="PENDING",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "invited_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="workspace_invitations_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invitations",
                        to="workspaces.workspace",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="workspace",
            constraint=models.CheckConstraint(
                condition=(
                    Q(("personal_owner__isnull", False), ("type", "PERSONAL"))
                    | Q(("personal_owner__isnull", True), ("type", "ORGANISATION"))
                ),
                name="workspace_personal_owner_matches_type",
            ),
        ),
        migrations.AddConstraint(
            model_name="workspacemembership",
            constraint=models.UniqueConstraint(
                fields=("user", "workspace"),
                name="workspace_membership_user_workspace_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="workspacemembership",
            index=models.Index(
                fields=["user", "workspace"],
                name="membership_user_workspace_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="workspacemembership",
            index=models.Index(
                fields=["workspace", "role"],
                name="membership_workspace_role_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="workspaceinvitation",
            constraint=models.UniqueConstraint(
                condition=Q(("status", "PENDING")),
                fields=("workspace", "email"),
                name="workspace_pending_invitation_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="workspaceinvitation",
            index=models.Index(
                fields=["workspace", "status"],
                name="invite_workspace_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="workspaceinvitation",
            index=models.Index(
                fields=["email", "status"],
                name="invitation_email_status_idx",
            ),
        ),
    ]
