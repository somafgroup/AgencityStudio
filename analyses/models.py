"""Project-owned Analysis containers and immutable canonical execution records."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class AnalysisKind(models.TextChoices):
    CANONICAL_SCALAR = "CANONICAL_SCALAR", _("Canonical scalar")


class AnalysisStatus(models.TextChoices):
    ACTIVE = "ACTIVE", _("Active")
    ARCHIVED = "ARCHIVED", _("Archived")


class RunStatus(models.TextChoices):
    QUEUED = "QUEUED", _("Queued")
    RUNNING = "RUNNING", _("Running")
    COMPLETED = "COMPLETED", _("Completed")
    FAILED = "FAILED", _("Failed")
    CANCELLED = "CANCELLED", _("Cancelled")


class SourceType(models.TextChoices):
    RAW_DATASET_VERSION = "RAW_DATASET_VERSION", _("Original Dataset Version")
    PREPARED_DATA = "PREPARED_DATA", _("Prepared Data")


class RunErrorCategory(models.TextChoices):
    LAB_VALIDATION_ERROR = "LAB_VALIDATION_ERROR", _("AgencityLab validation error")
    LAB_EXECUTION_ERROR = "LAB_EXECUTION_ERROR", _("AgencityLab execution error")
    SOURCE_ERROR = "SOURCE_ERROR", _("Source data error")
    STORAGE_ERROR = "STORAGE_ERROR", _("Result storage error")
    STUDIO_INTERNAL_ERROR = "STUDIO_INTERNAL_ERROR", _("Studio internal error")


class AnalysisQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status=AnalysisStatus.ACTIVE)

    def archived(self):
        return self.filter(status=AnalysisStatus.ARCHIVED)

    def for_project(self, project):
        return self.filter(project=project)

    def for_workspace(self, workspace):
        return self.filter(project__workspace=workspace)


class Analysis(models.Model):
    """Mutable user workspace whose historical executions live in immutable Runs."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="analyses"
    )
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    analysis_kind = models.CharField(
        max_length=32,
        choices=AnalysisKind.choices,
        default=AnalysisKind.CANONICAL_SCALAR,
    )
    status = models.CharField(
        max_length=16, choices=AnalysisStatus.choices, default=AnalysisStatus.ACTIVE
    )
    draft_configuration = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="analyses_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    objects = AnalysisQuerySet.as_manager()

    class Meta:
        ordering = ["-updated_at", "name"]
        indexes = [
            models.Index(fields=("project", "status", "-updated_at"), name="analysis_project_state_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class AnalysisRun(models.Model):
    """Immutable reproducibility boundary for one exact canonical execution."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE, related_name="runs")
    run_number = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=RunStatus.choices, default=RunStatus.QUEUED)

    source_type = models.CharField(max_length=32, choices=SourceType.choices)
    source_dataset_version = models.ForeignKey(
        "datasets.DatasetVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="analysis_runs",
    )
    source_prepared_artifact = models.ForeignKey(
        "datasets.PreparedDataArtifact",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="analysis_runs",
    )
    source_sha256 = models.CharField(max_length=64)
    source_snapshot = models.JSONField(default=dict)
    mapping_snapshot = models.JSONField(default=dict)

    system_revision = models.ForeignKey(
        "systems.SystemRevision", on_delete=models.PROTECT, related_name="analysis_runs"
    )
    system_observable = models.ForeignKey(
        "systems.ObservableDefinition", on_delete=models.PROTECT, related_name="analysis_runs"
    )
    system_configuration_fingerprint = models.CharField(max_length=64, blank=True)
    parameter_snapshot = models.JSONField(default=dict)
    analysis_options = models.JSONField(default=dict)

    agencitylab_version = models.CharField(max_length=32)
    studio_version = models.CharField(max_length=32)
    python_version = models.CharField(max_length=64)
    execution_fingerprint = models.CharField(max_length=64)
    result_sha256 = models.CharField(max_length=64, blank=True)
    effective_context = models.JSONField(default=dict, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    error_category = models.CharField(max_length=32, choices=RunErrorCategory.choices, blank=True)
    error_message = models.CharField(max_length=500, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="analysis_runs_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-run_number"]
        constraints = [
            models.UniqueConstraint(fields=("analysis", "run_number"), name="analysis_run_number_unique"),
            models.CheckConstraint(condition=Q(run_number__gt=0), name="analysis_run_number_positive"),
            models.CheckConstraint(
                condition=(
                    (Q(source_dataset_version__isnull=False) & Q(source_prepared_artifact__isnull=True))
                    | (Q(source_dataset_version__isnull=True) & Q(source_prepared_artifact__isnull=False))
                ),
                name="analysis_run_exactly_one_source",
            ),
        ]
        indexes = [
            models.Index(fields=("analysis", "-run_number"), name="analysis_run_order_idx"),
            models.Index(fields=("status", "-created_at"), name="analysis_run_status_idx"),
            models.Index(fields=("execution_fingerprint",), name="analysis_run_fingerprint_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            previous = AnalysisRun.objects.filter(pk=self.pk).values("status").first()
            if previous and previous["status"] in {
                RunStatus.COMPLETED,
                RunStatus.FAILED,
                RunStatus.CANCELLED,
            }:
                raise ValidationError(_("Finished AnalysisRuns are immutable."))
        return super().save(*args, **kwargs)

    @property
    def is_finished(self) -> bool:
        return self.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}

    def __str__(self) -> str:
        return f"{self.analysis} · Run {self.run_number}"


class AnalysisResultArtifact(models.Model):
    """Private immutable serialization of one completed public AgencityResult."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.OneToOneField(AnalysisRun, on_delete=models.CASCADE, related_name="result_artifact")
    storage_path = models.CharField(max_length=600, unique=True)
    format = models.CharField(max_length=32, default="ZIP_NPY_JSON")
    schema_version = models.CharField(max_length=16, default="1")
    sha256 = models.CharField(max_length=64)
    size_bytes = models.BigIntegerField()
    manifest = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(size_bytes__gte=0), name="analysis_result_size_nonnegative"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and AnalysisResultArtifact.objects.filter(pk=self.pk).exists():
            raise ValidationError(_("Analysis result artifacts are immutable."))
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.run} · canonical result"
