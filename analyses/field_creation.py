"""Creation boundary for experimental observable spatial field Analyses."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.translation import gettext as _

from datasets.field_source import FIELD_SOURCE_FORMAT, is_field_source
from datasets.models import Dataset, DatasetImportStatus, DatasetVersion
from projects.models import ProjectActivity
from workspaces.permissions import can_create_analysis

from .field_contract import FIELD_ANALYSIS_KIND, FIELD_SCIENTIFIC_STATUS
from .models import Analysis


def create_observable_field_analysis(
    *, actor, project, name: str, description: str, source: DatasetVersion
) -> Analysis:
    if not can_create_analysis(actor, project):
        raise PermissionDenied
    clean_name = str(name).strip()
    if not clean_name:
        raise ValidationError(_("Analysis name is required."))
    if not Dataset.objects.filter(pk=source.dataset_id, project=project).exists():
        raise ValidationError(_("The selected field source belongs to another Project."))
    if not Dataset.objects.filter(pk=source.dataset_id, current_version=source).exists():
        raise ValidationError(_("Select the confirmed current Dataset Version for the field source."))
    if source.import_status != DatasetImportStatus.READY or source.source_format != FIELD_SOURCE_FORMAT:
        raise ValidationError(_("Select a successfully inspected NPZ field source."))
    if not is_field_source(source):
        raise ValidationError(_("The selected NPZ source has not passed field-source inspection."))
    analysis = Analysis.objects.create(
        project=project,
        name=clean_name,
        description=str(description).strip(),
        analysis_kind=FIELD_ANALYSIS_KIND,
        created_by=actor,
        draft_configuration={
            "source_type": "RAW_DATASET_VERSION",
            "source_id": str(source.pk),
            "scientific_status": FIELD_SCIENTIFIC_STATUS,
            "configured": False,
        },
    )
    ProjectActivity.objects.create(
        project=project,
        actor=actor,
        event="ANALYSIS_CREATED",
        detail=_("Created EXPERIMENTAL observable spatial field Analysis %(name)s.")
        % {"name": analysis.name},
    )
    return analysis
