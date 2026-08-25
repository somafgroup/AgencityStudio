"""Durable Project models owned by Workspaces."""

import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class ProjectStatus(models.TextChoices):
    ACTIVE = "ACTIVE", _("Active")
    ARCHIVED = "ARCHIVED", _("Archived")


class ProjectQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status=ProjectStatus.ACTIVE)

    def archived(self):
        return self.filter(status=ProjectStatus.ARCHIVED)

    def for_workspace(self, workspace):
        return self.filter(workspace=workspace)


class Project(models.Model):
    """Workspace-owned container for durable scientific work."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey("workspaces.Workspace", on_delete=models.PROTECT, related_name="projects")
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=180)
    description = models.TextField(blank=True)
    domain = models.CharField(max_length=160, blank=True)
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=ProjectStatus.choices, default=ProjectStatus.ACTIVE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="projects_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    objects = ProjectQuerySet.as_manager()

    class Meta:
        ordering = ["-updated_at", "name"]
        constraints = [models.UniqueConstraint(fields=("workspace", "slug"), name="project_workspace_slug_unique")]
        indexes = [
            models.Index(fields=("workspace", "status"), name="project_ws_status_idx"),
            models.Index(fields=("workspace", "-updated_at"), name="project_ws_updated_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class ProjectActivityEvent(models.TextChoices):
    CREATED = "CREATED", _("Created")
    UPDATED = "UPDATED", _("Updated")
    ARCHIVED = "ARCHIVED", _("Archived")
    RESTORED = "RESTORED", _("Restored")
    DUPLICATED = "DUPLICATED", _("Duplicated")
    DATASET_CREATED = "DATASET_CREATED", _("Dataset created")
    DATASET_IMPORT = "DATASET_IMPORT", _("Dataset import started")
    DATASET_READY = "DATASET_READY", _("Dataset ready")
    DATASET_FAILED = "DATASET_FAILED", _("Dataset import failed")
    DATASET_VERSION = "DATASET_VERSION", _("Dataset version added")
    DATASET_UPDATED = "DATASET_UPDATED", _("Dataset updated")
    DATASET_DELETED = "DATASET_DELETED", _("Dataset deleted")
    PREP_CREATED = "PREP_CREATED", _("Preparation created")
    PREP_STARTED = "PREP_STARTED", _("Preparation started")
    PREP_READY = "PREP_READY", _("Preparation completed")
    PREP_FAILED = "PREP_FAILED", _("Preparation failed")
    PREP_DUPLICATED = "PREP_DUPLICATED", _("Preparation duplicated")
    PREP_DELETED = "PREP_DELETED", _("Preparation deleted")
    SYS_CREATED = "SYS_CREATED", _("System created")
    SYS_REVISED = "SYS_REVISED", _("System revised")
    SYS_DUPLICATED = "SYS_DUPLICATED", _("System duplicated")
    SYS_ARCHIVED = "SYS_ARCHIVED", _("System archived")
    SYS_RESTORED = "SYS_RESTORED", _("System restored")
    SYS_DELETED = "SYS_DELETED", _("System deleted")
    ANALYSIS_CREATED = "ANALYSIS_CREATED", _("Analysis created")
    ANALYSIS_UPDATED = "ANALYSIS_UPDATED", _("Analysis updated")
    ANALYSIS_RUN_QUEUED = "ANALYSIS_RUN_QUEUED", _("Analysis run queued")
    ANALYSIS_RUN_COMPLETED = "ANALYSIS_RUN_COMPLETED", _("Analysis run completed")
    ANALYSIS_RUN_FAILED = "ANALYSIS_RUN_FAILED", _("Analysis run failed")
    ANALYSIS_ARCHIVED = "ANALYSIS_ARCHIVED", _("Analysis archived")
    ANALYSIS_DELETED = "ANALYSIS_DELETED", _("Analysis deleted")
    DIAGNOSTIC_RUN_QUEUED = "DIAGNOSTIC_RUN_QUEUED", _("Diagnostic run queued")
    DIAGNOSTIC_RUN_COMPLETED = "DIAGNOSTIC_RUN_COMPLETED", _("Diagnostic run completed")
    DIAGNOSTIC_RUN_FAILED = "DIAGNOSTIC_RUN_FAILED", _("Diagnostic run failed")


class ProjectActivity(models.Model):
    """Lightweight application activity; not scientific provenance."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="activity")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="project_activity_events",
    )
    event = models.CharField(max_length=32, choices=ProjectActivityEvent.choices)
    detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=("project", "-created_at"), name="project_activity_time_idx")]

    def __str__(self) -> str:
        return f"{self.project} · {self.event}"
