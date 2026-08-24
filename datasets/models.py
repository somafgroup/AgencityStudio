"""Dataset metadata, immutable raw versions, and prepared-data provenance contracts."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class DatasetSourceKind(models.TextChoices):
    UPLOAD = "UPLOAD", _("Upload")
    PASTE = "PASTE", _("Pasted data")


class DatasetSourceFormat(models.TextChoices):
    CSV = "CSV", "CSV"
    TSV = "TSV", "TSV"
    TXT = "TXT", _("Structured text")
    XLSX = "XLSX", "XLSX"


class DatasetImportStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    PROCESSING = "PROCESSING", _("Inspecting")
    READY = "READY", _("Ready")
    FAILED = "FAILED", _("Failed")


class DatasetColumnType(models.TextChoices):
    NUMERIC = "NUMERIC", _("Numeric")
    DATETIME = "DATETIME", _("Date/time")
    BOOLEAN = "BOOLEAN", _("Boolean")
    TEXT = "TEXT", _("Text")
    MIXED = "MIXED", _("Mixed")
    EMPTY = "EMPTY", _("Empty")


class DatasetColumnRole(models.TextChoices):
    OTHER = "OTHER", _("Other")
    TIME = "TIME", _("Time")
    OBSERVABLE = "OBSERVABLE", _("Observable")


class DataPreparationStatus(models.TextChoices):
    DRAFT = "DRAFT", _("Draft")
    QUEUED = "QUEUED", _("Queued")
    PROCESSING = "PROCESSING", _("Processing")
    READY = "READY", _("Ready")
    FAILED = "FAILED", _("Failed")


class DatasetQuerySet(models.QuerySet):
    def for_workspace(self, workspace):
        return self.filter(project__workspace=workspace)

    def for_project(self, project):
        return self.filter(project=project)


class Dataset(models.Model):
    """Logical Project-owned dataset whose original raw sources are versioned separately."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="datasets",
    )
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=180)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="datasets_created",
    )
    current_version = models.ForeignKey(
        "DatasetVersion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = DatasetQuerySet.as_manager()

    class Meta:
        ordering = ["-updated_at", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=("project", "slug"),
                name="dataset_project_slug_unique",
            ),
        ]
        indexes = [
            models.Index(fields=("project", "-updated_at"), name="dataset_project_updated_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.current_version_id and self.pk:
            version_dataset_id = DatasetVersion.objects.filter(pk=self.current_version_id).values_list(
                "dataset_id", flat=True
            ).first()
            if version_dataset_id is not None and version_dataset_id != self.pk:
                raise ValidationError({"current_version": _("The current version belongs to another dataset.")})

    def __str__(self) -> str:
        return self.name


class DatasetVersion(models.Model):
    """Immutable original source snapshot plus reproducible import/inspection metadata."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    source_kind = models.CharField(max_length=16, choices=DatasetSourceKind.choices)
    source_format = models.CharField(max_length=16, choices=DatasetSourceFormat.choices)
    source_path = models.CharField(max_length=600, unique=True)
    original_filename = models.CharField(max_length=255)
    source_size_bytes = models.BigIntegerField()
    source_sha256 = models.CharField(max_length=64)
    media_type = models.CharField(max_length=160, blank=True)
    import_status = models.CharField(
        max_length=16,
        choices=DatasetImportStatus.choices,
        default=DatasetImportStatus.PENDING,
    )
    importer_id = models.CharField(max_length=64, blank=True)
    importer_schema_version = models.CharField(max_length=16, default="1")
    import_options = models.JSONField(default=dict, blank=True)
    detected_options = models.JSONField(default=dict, blank=True)
    inspection_generation = models.PositiveIntegerField(default=1)
    row_count = models.BigIntegerField(null=True, blank=True)
    column_count = models.PositiveIntegerField(null=True, blank=True)
    inspection_summary = models.JSONField(default=dict, blank=True)
    quality_issues = models.JSONField(default=list, blank=True)
    failure_summary = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dataset_versions_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dataset_versions_confirmed",
    )

    class Meta:
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=("dataset", "version_number"),
                name="dataset_version_number_unique",
            ),
            models.CheckConstraint(
                condition=Q(source_size_bytes__gte=0),
                name="dataset_version_size_nonnegative",
            ),
        ]
        indexes = [
            models.Index(fields=("dataset", "-version_number"), name="dataset_version_order_idx"),
            models.Index(fields=("import_status", "-created_at"), name="dataset_import_status_idx"),
        ]

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None

    def __str__(self) -> str:
        return f"{self.dataset} · v{self.version_number}"


class DatasetColumn(models.Model):
    """Position-stable column metadata inferred from one original DatasetVersion source."""

    dataset_version = models.ForeignKey(
        DatasetVersion,
        on_delete=models.CASCADE,
        related_name="columns",
    )
    position = models.PositiveIntegerField(help_text=_("One-based source column position."))
    source_name = models.CharField(max_length=255, blank=True)
    display_name = models.CharField(max_length=255)
    inferred_type = models.CharField(max_length=16, choices=DatasetColumnType.choices)
    role = models.CharField(
        max_length=16,
        choices=DatasetColumnRole.choices,
        default=DatasetColumnRole.OTHER,
    )
    unit = models.CharField(max_length=80, blank=True)
    missing_count = models.BigIntegerField(default=0)
    non_numeric_count = models.BigIntegerField(default=0)
    non_finite_count = models.BigIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=("dataset_version", "position"),
                name="dataset_column_position_unique",
            ),
            models.UniqueConstraint(
                fields=("dataset_version",),
                condition=Q(role=DatasetColumnRole.TIME),
                name="dataset_single_time_column",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.dataset_version} · {self.display_name}"


class DataPreparation(models.Model):
    """Ordered, source-version-pinned recipe for one immutable prepared-data result."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_version = models.ForeignKey(
        DatasetVersion,
        on_delete=models.PROTECT,
        related_name="preparations",
    )
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=DataPreparationStatus.choices,
        default=DataPreparationStatus.DRAFT,
    )
    recipe = models.JSONField(default=list, blank=True)
    recipe_hash = models.CharField(max_length=64, blank=True)
    engine_id = models.CharField(max_length=80, blank=True)
    engine_version = models.CharField(max_length=32, blank=True)
    studio_version = models.CharField(max_length=32, blank=True)
    python_version = models.CharField(max_length=64, blank=True)
    dependency_versions = models.JSONField(default=dict, blank=True)
    execution_metadata = models.JSONField(default=dict, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    failure_summary = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="data_preparations_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=("source_version", "status", "-created_at"),
                name="data_prep_source_status_idx",
            ),
        ]

    @property
    def dataset(self) -> Dataset:
        return self.source_version.dataset

    def __str__(self) -> str:
        return f"{self.name} · {self.get_status_display()}"


class PreparedDataArtifact(models.Model):
    """Immutable materialized result produced by exactly one DataPreparation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    preparation = models.OneToOneField(
        DataPreparation,
        on_delete=models.CASCADE,
        related_name="artifact",
    )
    storage_path = models.CharField(max_length=600, unique=True)
    output_format = models.CharField(max_length=16, default="CSV")
    media_type = models.CharField(max_length=160, default="text/csv")
    size_bytes = models.BigIntegerField()
    prepared_sha256 = models.CharField(max_length=64)
    row_count = models.BigIntegerField()
    column_count = models.PositiveIntegerField()
    column_metadata = models.JSONField(default=list)
    inspection_summary = models.JSONField(default=dict, blank=True)
    quality_issues = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(size_bytes__gte=0),
                name="prepared_artifact_size_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(row_count__gte=0),
                name="prepared_artifact_rows_nonnegative",
            ),
        ]

    def __str__(self) -> str:
        return f"Prepared · {self.preparation.name}"
