"""Immutable multiscale and CRM-window sensitivity study records."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class StudyType(models.TextChoices):
    TAU_MULTISCALE = "TAU_MULTISCALE", _("Tau multiscale")
    W_SENSITIVITY = "W_SENSITIVITY", _("Window sensitivity")


class GridType(models.TextChoices):
    EXPLICIT = "EXPLICIT", _("Explicit list")
    LINEAR = "LINEAR", _("Linear range")
    LOG = "LOG", _("Logarithmic range")


class StudyStatus(models.TextChoices):
    DRAFT = "DRAFT", _("Draft")
    QUEUED = "QUEUED", _("Queued")
    RUNNING = "RUNNING", _("Running")
    COMPLETED = "COMPLETED", _("Completed")
    FAILED = "FAILED", _("Failed")
    CANCELLED = "CANCELLED", _("Cancelled")


class SensitivityErrorCategory(models.TextChoices):
    LAB_SENSITIVITY_VALIDATION_ERROR = (
        "LAB_SENSITIVITY_VALIDATION_ERROR",
        _("AgencityLab sensitivity validation error"),
    )
    LAB_SENSITIVITY_EXECUTION_ERROR = (
        "LAB_SENSITIVITY_EXECUTION_ERROR",
        _("AgencityLab sensitivity execution error"),
    )
    RESULT_INPUT_ERROR = "RESULT_INPUT_ERROR", _("Base run input error")
    STORAGE_ERROR = "STORAGE_ERROR", _("Sensitivity result storage error")
    STUDIO_INTERNAL_ERROR = "STUDIO_INTERNAL_ERROR", _("Studio internal error")


class SensitivityStudy(models.Model):
    """Immutable execution contract derived from one completed AnalysisRun."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analysis_run = models.ForeignKey(
        "analyses.AnalysisRun",
        on_delete=models.PROTECT,
        related_name="sensitivity_studies",
    )
    study_number = models.PositiveIntegerField()
    study_type = models.CharField(max_length=32, choices=StudyType.choices)
    status = models.CharField(max_length=16, choices=StudyStatus.choices, default=StudyStatus.QUEUED)

    canonical_result_sha256 = models.CharField(max_length=64)
    source_sha256 = models.CharField(max_length=64)
    system_revision = models.ForeignKey(
        "systems.SystemRevision",
        on_delete=models.PROTECT,
        related_name="sensitivity_studies",
    )
    system_configuration_fingerprint = models.CharField(max_length=64, blank=True)
    mapping_snapshot = models.JSONField(default=dict)
    fixed_parameter_snapshot = models.JSONField(default=dict)

    grid_type = models.CharField(max_length=16, choices=GridType.choices)
    grid_unit = models.CharField(max_length=80)
    requested_grid = models.JSONField(default=list)
    study_configuration = models.JSONField(default=dict)
    public_api_identifier = models.CharField(max_length=160)
    scientific_status = models.CharField(max_length=64, default="SENSITIVITY_STUDY")

    agencitylab_version = models.CharField(max_length=32)
    studio_version = models.CharField(max_length=32)
    python_version = models.CharField(max_length=64)
    execution_fingerprint = models.CharField(max_length=64)
    result_sha256 = models.CharField(max_length=64, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    error_category = models.CharField(
        max_length=48,
        choices=SensitivityErrorCategory.choices,
        blank=True,
    )
    error_message = models.CharField(max_length=500, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sensitivity_studies_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-study_number"]
        constraints = [
            models.UniqueConstraint(
                fields=("analysis_run", "study_number"),
                name="sensitivity_study_number_unique",
            ),
            models.CheckConstraint(
                condition=Q(study_number__gt=0),
                name="sensitivity_study_number_positive",
            ),
        ]
        indexes = [
            models.Index(fields=("analysis_run", "-study_number"), name="sensitivity_order_idx"),
            models.Index(fields=("status", "-created_at"), name="sensitivity_status_idx"),
            models.Index(fields=("execution_fingerprint",), name="sensitivity_fp_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            previous = SensitivityStudy.objects.filter(pk=self.pk).values("status").first()
            if previous and previous["status"] in {
                StudyStatus.COMPLETED,
                StudyStatus.FAILED,
                StudyStatus.CANCELLED,
            }:
                raise ValidationError(_("Finished sensitivity studies are immutable."))
        return super().save(*args, **kwargs)

    @property
    def is_finished(self) -> bool:
        return self.status in {
            StudyStatus.COMPLETED,
            StudyStatus.FAILED,
            StudyStatus.CANCELLED,
        }

    def __str__(self) -> str:
        return f"{self.analysis_run} · Sensitivity {self.study_number}"


class SensitivityResultArtifact(models.Model):
    """Private immutable serialization of one completed sensitivity study."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    study = models.OneToOneField(
        SensitivityStudy,
        on_delete=models.CASCADE,
        related_name="result_artifact",
    )
    storage_path = models.CharField(max_length=600, unique=True)
    format = models.CharField(max_length=32, default="ZIP_NPY_JSON")
    schema_version = models.CharField(max_length=16, default="1")
    sha256 = models.CharField(max_length=64)
    size_bytes = models.BigIntegerField()
    manifest = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(size_bytes__gte=0),
                name="sensitivity_result_size_nonnegative",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and SensitivityResultArtifact.objects.filter(pk=self.pk).exists():
            raise ValidationError(_("Sensitivity result artifacts are immutable."))
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.study} · sensitivity result"
