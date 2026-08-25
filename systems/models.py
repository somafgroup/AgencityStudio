"""Project-owned scientific System identities and immutable context revisions."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class SystemStatus(models.TextChoices):
    ACTIVE = "ACTIVE", _("Active")
    ARCHIVED = "ARCHIVED", _("Archived")


class RevisionDocumentationStatus(models.TextChoices):
    DRAFT = "DRAFT", _("Draft")
    DOCUMENTED = "DOCUMENTED", _("Documented")


class ObservableNature(models.TextChoices):
    MEASUREMENT = "MEASUREMENT", _("Measurement")
    SIMULATION = "SIMULATION", _("Simulation")
    DERIVED = "DERIVED", _("Derived physical quantity")
    OTHER = "OTHER", _("Other")


class ParameterOrigin(models.TextChoices):
    PHYSICAL_MEASUREMENT = "PHYSICAL_MEASUREMENT", _("Physical measurement")
    CALIBRATION = "CALIBRATION", _("Calibration")
    MANUFACTURER = "MANUFACTURER", _("Manufacturer specification")
    LITERATURE = "LITERATURE", _("Scientific literature")
    MODEL = "MODEL", _("Model specification")
    PROTOCOL = "PROTOCOL", _("Experimental protocol")
    CONVENTION = "CONVENTION", _("Convention")
    OTHER = "OTHER", _("Other")


class MemoryWindowMode(models.TextChoices):
    UNSPECIFIED = "UNSPECIFIED", _("Unspecified")
    EXPLICIT = "EXPLICIT", _("Explicit")


class CharacteristicPowerMode(models.TextChoices):
    FIXED = "FIXED", _("Fixed scalar")


class SystemQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status=SystemStatus.ACTIVE)

    def archived(self):
        return self.filter(status=SystemStatus.ARCHIVED)

    def for_project(self, project):
        return self.filter(project=project)


class System(models.Model):
    """Stable Project-owned identity for one studied scientific/physical system."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="systems",
    )
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=180)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=SystemStatus.choices,
        default=SystemStatus.ACTIVE,
    )
    current_revision = models.ForeignKey(
        "SystemRevision",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        editable=False,
    )
    duplicated_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="duplicates",
        editable=False,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="systems_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    objects = SystemQuerySet.as_manager()

    class Meta:
        ordering = ["-updated_at", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=("project", "slug"),
                name="system_project_slug_unique",
            ),
        ]
        indexes = [
            models.Index(fields=("project", "status", "-updated_at"), name="system_project_state_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.current_revision_id and self.pk:
            revision_system_id = (
                SystemRevision.objects.filter(pk=self.current_revision_id)
                .values_list("system_id", flat=True)
                .first()
            )
            if revision_system_id is not None and revision_system_id != self.pk:
                raise ValidationError(
                    {"current_revision": _("The current revision belongs to another system.")}
                )

    def __str__(self) -> str:
        return self.name


class SystemRevision(models.Model):
    """Immutable scientific-context snapshot for one System."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    system = models.ForeignKey(System, on_delete=models.CASCADE, related_name="revisions")
    revision_number = models.PositiveIntegerField()
    documentation_status = models.CharField(
        max_length=16,
        choices=RevisionDocumentationStatus.choices,
        default=RevisionDocumentationStatus.DRAFT,
    )

    description = models.TextField(blank=True)
    domain = models.CharField(max_length=160, blank=True)
    system_type = models.CharField(max_length=160, blank=True)
    mechanism = models.TextField(blank=True)
    environment = models.CharField(max_length=160, blank=True)
    measurement_context = models.TextField(blank=True)
    scientific_notes = models.TextField(blank=True)
    revision_reason = models.TextField(blank=True)

    a_ref_value = models.FloatField(null=True, blank=True)
    a_ref_value_text = models.CharField(max_length=80, blank=True)
    a_ref_unit = models.CharField(max_length=80, blank=True)
    a_ref_origin = models.CharField(max_length=32, choices=ParameterOrigin.choices, blank=True)
    a_ref_origin_detail = models.CharField(max_length=255, blank=True)
    a_ref_justification = models.TextField(blank=True)

    tau_value = models.FloatField(null=True, blank=True)
    tau_value_text = models.CharField(max_length=80, blank=True)
    tau_unit = models.CharField(max_length=80, blank=True)
    tau_origin = models.CharField(max_length=32, choices=ParameterOrigin.choices, blank=True)
    tau_origin_detail = models.CharField(max_length=255, blank=True)
    tau_justification = models.TextField(blank=True)

    w_mode = models.CharField(
        max_length=16,
        choices=MemoryWindowMode.choices,
        default=MemoryWindowMode.UNSPECIFIED,
    )
    w_value = models.FloatField(null=True, blank=True)
    w_value_text = models.CharField(max_length=80, blank=True)
    w_unit = models.CharField(max_length=80, blank=True)
    w_origin = models.CharField(max_length=32, choices=ParameterOrigin.choices, blank=True)
    w_origin_detail = models.CharField(max_length=255, blank=True)
    w_justification = models.TextField(blank=True)

    p_c_mode = models.CharField(
        max_length=16,
        choices=CharacteristicPowerMode.choices,
        default=CharacteristicPowerMode.FIXED,
    )
    p_c_value = models.FloatField(null=True, blank=True)
    p_c_value_text = models.CharField(max_length=80, blank=True)
    p_c_unit = models.CharField(max_length=80, blank=True)
    p_c_origin = models.CharField(max_length=32, choices=ParameterOrigin.choices, blank=True)
    p_c_origin_detail = models.CharField(max_length=255, blank=True)
    p_c_justification = models.TextField(blank=True)

    configuration_fingerprint = models.CharField(max_length=64, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="system_revisions_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-revision_number"]
        constraints = [
            models.UniqueConstraint(
                fields=("system", "revision_number"),
                name="system_revision_number_unique",
            ),
            models.CheckConstraint(
                condition=Q(revision_number__gt=0),
                name="system_revision_number_positive",
            ),
        ]
        indexes = [
            models.Index(fields=("system", "-revision_number"), name="system_revision_order_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and SystemRevision.objects.filter(pk=self.pk).exists():
            raise ValidationError(_("Historical scientific revisions are immutable."))
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.system} · Revision {self.revision_number}"


class ObservableDefinition(models.Model):
    """Scientific meaning of one observable within an immutable SystemRevision."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(
        SystemRevision,
        on_delete=models.CASCADE,
        related_name="observables",
    )
    position = models.PositiveIntegerField()
    name = models.CharField(max_length=180)
    symbol = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=80, blank=True)
    observable_kind = models.CharField(max_length=120, blank=True)
    nature = models.CharField(max_length=16, choices=ObservableNature.choices)
    source_description = models.TextField(blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=("revision", "position"),
                name="system_observable_position_unique",
            ),
            models.UniqueConstraint(
                fields=("revision",),
                condition=Q(is_primary=True),
                name="system_single_primary_observable",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and ObservableDefinition.objects.filter(pk=self.pk).exists():
            raise ValidationError(_("Observable definitions in historical revisions are immutable."))
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class ScientificReference(models.Model):
    """Lightweight citation attached to one immutable SystemRevision."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(
        SystemRevision,
        on_delete=models.CASCADE,
        related_name="references",
    )
    title = models.CharField(max_length=255, blank=True)
    citation = models.TextField()
    doi = models.CharField(max_length=255, blank=True)
    url = models.URLField(max_length=500, blank=True)
    notes = models.TextField(blank=True)
    supports_a_ref = models.BooleanField(default=False)
    supports_tau = models.BooleanField(default=False)
    supports_w = models.BooleanField(default=False)
    supports_p_c = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]

    def save(self, *args, **kwargs):
        if self.pk and ScientificReference.objects.filter(pk=self.pk).exists():
            raise ValidationError(_("References in historical revisions are immutable."))
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.title or self.citation[:80]
