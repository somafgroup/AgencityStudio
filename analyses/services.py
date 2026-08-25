"""Transactional lifecycle and reproducibility services for canonical Analyses."""

from __future__ import annotations

import hashlib
import json
import platform
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.http import Http404
from django.utils import timezone
from django.utils.translation import gettext as _

from datasets.models import DatasetVersion, PreparedDataArtifact
from labbridge.service import get_lab_version
from projects.models import ProjectActivity
from systems.models import ObservableDefinition, SystemRevision
from workspaces.permissions import (
    can_archive_analysis,
    can_create_analysis,
    can_delete_analysis,
    can_edit_analysis,
    can_restore_analysis,
    can_run_analysis,
    can_view_analysis,
)

from .models import Analysis, AnalysisKind, AnalysisRun, AnalysisStatus, RunStatus, SourceType
from .results import RESULT_SCHEMA_VERSION
from .sources import SourceContractError, descriptor_for, materialize_vectors
from .validation import (
    validate_mapping,
    validate_parameter_contract,
    validate_sample_contract,
    validate_units,
)


def _version(name: str) -> str:
    try:
        return package_version(name)
    except PackageNotFoundError:
        return "not-installed"


def software_context() -> dict:
    return {
        "studio_version": _version("agencitystudio"),
        "agencitylab_version": get_lab_version(),
        "python_version": platform.python_version(),
    }


def _record(analysis: Analysis, *, actor, event: str, detail: str = "") -> None:
    ProjectActivity.objects.create(
        project=analysis.project,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        event=event,
        detail=detail[:255],
    )


def _fingerprint(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _next_run_number(analysis: Analysis) -> int:
    latest = AnalysisRun.objects.filter(analysis=analysis).aggregate(value=Max("run_number"))[
        "value"
    ]
    return (latest or 0) + 1


def _enqueue(run_id) -> None:
    from .tasks import execute_analysis_run

    execute_analysis_run.delay(str(run_id))


def get_analysis_or_404(*, user, analysis_id) -> Analysis:
    try:
        analysis = Analysis.objects.select_related(
            "project", "project__workspace", "created_by"
        ).get(pk=analysis_id)
    except (Analysis.DoesNotExist, ValueError) as exc:
        raise Http404 from exc
    if not can_view_analysis(user, analysis):
        raise Http404
    return analysis


@transaction.atomic
def create_analysis(
    *,
    actor,
    project,
    name: str,
    description: str = "",
    source_type: str,
    source_id: str,
) -> Analysis:
    if not can_create_analysis(actor, project):
        raise PermissionDenied
    clean_name = str(name).strip()
    if not clean_name:
        raise ValidationError(_("Analysis name is required."))
    if len(clean_name) > 180:
        raise ValidationError(_("Analysis name must be 180 characters or fewer."))
    if source_type == SourceType.RAW_DATASET_VERSION:
        source = DatasetVersion.objects.select_related("dataset", "dataset__project").get(
            pk=source_id, dataset__project=project
        )
        descriptor = descriptor_for(dataset_version=source)
    elif source_type == SourceType.PREPARED_DATA:
        source = PreparedDataArtifact.objects.select_related(
            "preparation",
            "preparation__source_version",
            "preparation__source_version__dataset",
        ).get(pk=source_id, preparation__source_version__dataset__project=project)
        descriptor = descriptor_for(prepared_artifact=source)
    else:
        raise ValidationError(_("Select a supported analysis source."))
    analysis = Analysis.objects.create(
        project=project,
        name=clean_name,
        description=str(description).strip(),
        analysis_kind=AnalysisKind.CANONICAL_SCALAR,
        created_by=actor,
        draft_configuration={
            "source_type": descriptor.source_type,
            "source_id": descriptor.source_id,
        },
    )
    _record(
        analysis,
        actor=actor,
        event="ANALYSIS_CREATED",
        detail=_("Created canonical Analysis %(name)s.") % {"name": analysis.name},
    )
    return analysis


def _resolve_source(analysis: Analysis, config: dict):
    source_type = config.get("source_type")
    source_id = config.get("source_id")
    if source_type == SourceType.RAW_DATASET_VERSION:
        source = (
            DatasetVersion.objects.select_related("dataset", "dataset__project")
            .prefetch_related("columns")
            .get(pk=source_id, dataset__project=analysis.project)
        )
        return source, None, descriptor_for(dataset_version=source)
    if source_type == SourceType.PREPARED_DATA:
        source = PreparedDataArtifact.objects.select_related(
            "preparation",
            "preparation__source_version",
            "preparation__source_version__dataset",
        ).get(pk=source_id, preparation__source_version__dataset__project=analysis.project)
        return None, source, descriptor_for(prepared_artifact=source)
    raise SourceContractError(
        "The Analysis draft does not identify a supported pinned source."
    )


@transaction.atomic
def configure_analysis(
    *,
    actor,
    analysis: Analysis,
    coordinate_position: int,
    observable_position: int,
    system_revision: SystemRevision,
    system_observable: ObservableDefinition,
    options: dict | None = None,
) -> Analysis:
    if not can_edit_analysis(actor, analysis):
        raise PermissionDenied
    locked = Analysis.objects.select_for_update().select_related("project").get(pk=analysis.pk)
    if locked.status != AnalysisStatus.ACTIVE:
        raise ValidationError(_("Restore the Analysis before changing its configuration."))
    if system_revision.system.project_id != locked.project_id:
        raise ValidationError(_("The selected System Revision belongs to another Project."))
    if system_observable.revision_id != system_revision.pk:
        raise ValidationError(
            _("The selected System observable does not belong to that revision.")
        )
    _, _, descriptor = _resolve_source(locked, locked.draft_configuration)
    coordinate, observable = validate_mapping(
        descriptor,
        coordinate_position=int(coordinate_position),
        observable_position=int(observable_position),
    )
    validate_parameter_contract(system_revision)
    unit_warnings = validate_units(
        coordinate=coordinate,
        observable=observable,
        revision=system_revision,
        system_observable=system_observable,
    )
    selected_options = dict(options or {})
    defaults = {
        "domain": system_revision.domain,
        "mechanism": system_revision.mechanism,
        "system_type": system_revision.system_type,
        "environment": system_revision.environment,
        "geometry": "",
    }
    normalized_options = {
        key: str(selected_options.get(key, defaults[key]) or defaults[key]).strip()
        for key in defaults
    }
    locked.draft_configuration = {
        "source_type": descriptor.source_type,
        "source_id": descriptor.source_id,
        "coordinate_position": int(coordinate_position),
        "observable_position": int(observable_position),
        "system_revision_id": str(system_revision.pk),
        "system_observable_id": str(system_observable.pk),
        "options": normalized_options,
        "preflight_warnings": unit_warnings,
    }
    locked.save(update_fields=("draft_configuration", "updated_at"))
    _record(
        locked,
        actor=actor,
        event="ANALYSIS_UPDATED",
        detail=_("Updated Analysis configuration."),
    )
    return locked


def review_snapshot(analysis: Analysis) -> dict:
    config = dict(analysis.draft_configuration or {})
    raw, prepared, descriptor = _resolve_source(analysis, config)
    revision = SystemRevision.objects.select_related("system").get(
        pk=config.get("system_revision_id"), system__project=analysis.project
    )
    observable_def = ObservableDefinition.objects.get(
        pk=config.get("system_observable_id"), revision=revision
    )
    coordinate, observable = validate_mapping(
        descriptor,
        coordinate_position=int(config["coordinate_position"]),
        observable_position=int(config["observable_position"]),
    )
    parameters = validate_parameter_contract(revision)
    warnings = [*config.get("preflight_warnings", []), *descriptor.quality_issues]
    return {
        "descriptor": descriptor,
        "coordinate": coordinate,
        "observable": observable,
        "revision": revision,
        "system_observable": observable_def,
        "parameters": parameters,
        "options": dict(config.get("options") or {}),
        "warnings": warnings,
        "raw": raw,
        "prepared": prepared,
    }


def _mapping_snapshot(*, coordinate: dict, observable: dict, system_observable) -> dict:
    return {
        "time": {**coordinate},
        "observable": {
            **observable,
            "system_observable_id": str(system_observable.pk),
            "system_observable_name": system_observable.name,
        },
    }


def _source_snapshot(descriptor) -> dict:
    return {
        "type": descriptor.source_type,
        "id": descriptor.source_id,
        "sha256": descriptor.sha256,
        "rows": descriptor.rows,
        "columns": descriptor.columns,
        "lineage": descriptor.lineage,
    }


@transaction.atomic
def queue_analysis_run(*, actor, analysis: Analysis) -> AnalysisRun:
    if not can_run_analysis(actor, analysis):
        raise PermissionDenied
    locked = Analysis.objects.select_for_update().select_related("project").get(pk=analysis.pk)
    if locked.status != AnalysisStatus.ACTIVE:
        raise ValidationError(_("Restore the Analysis before running it."))
    snapshot = review_snapshot(locked)
    raw, prepared = snapshot["raw"], snapshot["prepared"]
    xi, u = materialize_vectors(
        dataset_version=raw,
        prepared_artifact=prepared,
        coordinate_position=snapshot["coordinate"]["position"],
        observable_position=snapshot["observable"]["position"],
    )
    params = snapshot["parameters"]
    validate_sample_contract(
        xi,
        u,
        requested_w=params["w"]["requested_value"],
        tau=params["tau"]["value"],
    )
    context = software_context()
    if context["agencitylab_version"] != "1.1.3":
        raise ValidationError(
            _("AgencityLab 1.1.3 is required for this Analysis contract.")
        )
    mapping = _mapping_snapshot(
        coordinate=snapshot["coordinate"],
        observable=snapshot["observable"],
        system_observable=snapshot["system_observable"],
    )
    source_snapshot = _source_snapshot(snapshot["descriptor"])
    execution_payload = {
        "source_sha256": snapshot["descriptor"].sha256,
        "source_type": snapshot["descriptor"].source_type,
        "mapping": mapping,
        "system_revision_id": str(snapshot["revision"].pk),
        "system_configuration_fingerprint": snapshot[
            "revision"
        ].configuration_fingerprint,
        "parameters": params,
        "options": snapshot["options"],
        "agencitylab_version": context["agencitylab_version"],
        "result_schema_version": RESULT_SCHEMA_VERSION,
    }
    run = AnalysisRun.objects.create(
        analysis=locked,
        run_number=_next_run_number(locked),
        status=RunStatus.QUEUED,
        source_type=snapshot["descriptor"].source_type,
        source_dataset_version=raw,
        source_prepared_artifact=prepared,
        source_sha256=snapshot["descriptor"].sha256,
        source_snapshot=source_snapshot,
        mapping_snapshot=mapping,
        system_revision=snapshot["revision"],
        system_observable=snapshot["system_observable"],
        system_configuration_fingerprint=snapshot[
            "revision"
        ].configuration_fingerprint,
        parameter_snapshot=params,
        analysis_options=snapshot["options"],
        agencitylab_version=context["agencitylab_version"],
        studio_version=context["studio_version"],
        python_version=context["python_version"],
        execution_fingerprint=_fingerprint(execution_payload),
        warnings=list(snapshot["warnings"]),
        created_by=actor,
        queued_at=timezone.now(),
    )
    _record(
        locked,
        actor=actor,
        event="ANALYSIS_RUN_QUEUED",
        detail=_("Queued Analysis Run %(number)s.") % {"number": run.run_number},
    )
    transaction.on_commit(lambda: _enqueue(run.pk))
    return run


@transaction.atomic
def rerun_analysis_run(*, actor, run: AnalysisRun) -> AnalysisRun:
    """Queue a new Run from an immutable historical Run, not the mutable Analysis draft."""
    locked_analysis = (
        Analysis.objects.select_for_update()
        .select_related("project")
        .get(pk=run.analysis_id)
    )
    if not can_run_analysis(actor, locked_analysis):
        raise PermissionDenied
    if locked_analysis.status != AnalysisStatus.ACTIVE:
        raise ValidationError(_("Restore the Analysis before running it again."))
    source_run = AnalysisRun.objects.select_related(
        "source_dataset_version",
        "source_prepared_artifact",
        "system_revision",
        "system_observable",
    ).get(pk=run.pk, analysis=locked_analysis)
    raw = source_run.source_dataset_version
    prepared = source_run.source_prepared_artifact
    descriptor = descriptor_for(dataset_version=raw) if raw else descriptor_for(prepared_artifact=prepared)
    if descriptor.sha256 != source_run.source_sha256:
        raise ValidationError(_("The pinned source hash no longer matches the historical Run."))
    time_mapping = source_run.mapping_snapshot["time"]
    observable_mapping = source_run.mapping_snapshot["observable"]
    xi, u = materialize_vectors(
        dataset_version=raw,
        prepared_artifact=prepared,
        coordinate_position=int(time_mapping["position"]),
        observable_position=int(observable_mapping["position"]),
    )
    params = source_run.parameter_snapshot
    validate_sample_contract(
        xi,
        u,
        requested_w=params["w"].get("requested_value"),
        tau=float(params["tau"]["value"]),
    )
    context = software_context()
    if context["agencitylab_version"] != source_run.agencitylab_version:
        raise ValidationError(
            _("Exact rerun requires the same AgencityLab version as the historical Run.")
        )
    rerun = AnalysisRun.objects.create(
        analysis=locked_analysis,
        run_number=_next_run_number(locked_analysis),
        status=RunStatus.QUEUED,
        source_type=source_run.source_type,
        source_dataset_version=raw,
        source_prepared_artifact=prepared,
        source_sha256=source_run.source_sha256,
        source_snapshot=source_run.source_snapshot,
        mapping_snapshot=source_run.mapping_snapshot,
        system_revision=source_run.system_revision,
        system_observable=source_run.system_observable,
        system_configuration_fingerprint=source_run.system_configuration_fingerprint,
        parameter_snapshot=source_run.parameter_snapshot,
        analysis_options=source_run.analysis_options,
        agencitylab_version=context["agencitylab_version"],
        studio_version=context["studio_version"],
        python_version=context["python_version"],
        execution_fingerprint=source_run.execution_fingerprint,
        warnings=[],
        created_by=actor,
        queued_at=timezone.now(),
    )
    _record(
        locked_analysis,
        actor=actor,
        event="ANALYSIS_RUN_QUEUED",
        detail=_("Queued exact rerun %(number)s from Run %(source)s.")
        % {"number": rerun.run_number, "source": source_run.run_number},
    )
    transaction.on_commit(lambda: _enqueue(rerun.pk))
    return rerun


@transaction.atomic
def cancel_analysis_run(*, actor, run: AnalysisRun) -> AnalysisRun:
    locked = (
        AnalysisRun.objects.select_for_update()
        .select_related("analysis", "analysis__project")
        .get(pk=run.pk)
    )
    if not can_run_analysis(actor, locked.analysis):
        raise PermissionDenied
    if locked.status == RunStatus.RUNNING:
        raise ValidationError(
            _("A running AgencityLab call cannot be safely cancelled cooperatively.")
        )
    if locked.status != RunStatus.QUEUED:
        raise ValidationError(_("Only a queued Run can be cancelled."))
    locked.status = RunStatus.CANCELLED
    locked.completed_at = timezone.now()
    locked.save(update_fields=("status", "completed_at"))
    return locked


@transaction.atomic
def archive_analysis(*, actor, analysis: Analysis) -> Analysis:
    if not can_archive_analysis(actor, analysis):
        raise PermissionDenied
    locked = Analysis.objects.select_for_update().get(pk=analysis.pk)
    locked.status = AnalysisStatus.ARCHIVED
    locked.archived_at = timezone.now()
    locked.save(update_fields=("status", "archived_at", "updated_at"))
    _record(locked, actor=actor, event="ANALYSIS_ARCHIVED")
    return locked


@transaction.atomic
def restore_analysis(*, actor, analysis: Analysis) -> Analysis:
    if not can_restore_analysis(actor, analysis):
        raise PermissionDenied
    locked = Analysis.objects.select_for_update().get(pk=analysis.pk)
    locked.status = AnalysisStatus.ACTIVE
    locked.archived_at = None
    locked.save(update_fields=("status", "archived_at", "updated_at"))
    return locked


@transaction.atomic
def delete_analysis(*, actor, analysis: Analysis) -> None:
    if not can_delete_analysis(actor, analysis):
        raise PermissionDenied
    locked = Analysis.objects.select_for_update().get(pk=analysis.pk)
    if locked.runs.filter(status__in=(RunStatus.QUEUED, RunStatus.RUNNING)).exists():
        raise ValidationError(_("Queued or running Analyses cannot be deleted."))
    paths = list(
        locked.runs.filter(result_artifact__isnull=False).values_list(
            "result_artifact__storage_path", flat=True
        )
    )
    _record(
        locked,
        actor=actor,
        event="ANALYSIS_DELETED",
        detail=_("Deleted Analysis %(name)s.") % {"name": locked.name},
    )
    locked.delete()
    if paths:
        from .storage import analysis_storage

        transaction.on_commit(lambda: [analysis_storage().delete(path) for path in paths])