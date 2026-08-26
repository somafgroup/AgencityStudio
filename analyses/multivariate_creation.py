"""Creation service for Multivariate Analyses using the shared Analysis model."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from datasets.models import DatasetVersion, PreparedDataArtifact
from projects.models import ProjectActivity
from workspaces.permissions import can_create_analysis

from .models import Analysis, AnalysisKind, SourceType
from .sources import descriptor_for


@transaction.atomic
def create_multivariate_analysis(
    *,
    actor,
    project,
    name: str,
    description: str = "",
    source_type: str,
    source_id: str,
) -> Analysis:
    """Create a multivariate Analysis draft pinned to one exact source identity."""
    if not can_create_analysis(actor, project):
        raise PermissionDenied
    clean_name = str(name).strip()
    if not clean_name:
        raise ValidationError(_("Analysis name is required."))
    if len(clean_name) > 180:
        raise ValidationError(_("Analysis name must be 180 characters or fewer."))
    if source_type == SourceType.RAW_DATASET_VERSION:
        source = DatasetVersion.objects.select_related("dataset", "dataset__project").get(
            pk=source_id,
            dataset__project=project,
        )
        descriptor = descriptor_for(dataset_version=source)
    elif source_type == SourceType.PREPARED_DATA:
        source = PreparedDataArtifact.objects.select_related(
            "preparation",
            "preparation__source_version",
            "preparation__source_version__dataset",
        ).get(
            pk=source_id,
            preparation__source_version__dataset__project=project,
        )
        descriptor = descriptor_for(prepared_artifact=source)
    else:
        raise ValidationError(_("Select a supported analysis source."))
    analysis = Analysis.objects.create(
        project=project,
        name=clean_name,
        description=str(description).strip(),
        analysis_kind=AnalysisKind.MULTIVARIATE,
        created_by=actor,
        draft_configuration={
            "source_type": descriptor.source_type,
            "source_id": descriptor.source_id,
        },
    )
    ProjectActivity.objects.create(
        project=project,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        event="ANALYSIS_CREATED",
        detail=_("Created multivariate Analysis %(name)s.") % {"name": analysis.name},
    )
    return analysis
