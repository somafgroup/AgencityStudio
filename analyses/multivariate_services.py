"""Transactional configuration and immutable execution snapshots for multivariate Analysis."""

from __future__ import annotations

from copy import deepcopy

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from labbridge.multivariate import (
    MULTIVARIATE_PUBLIC_FUNCTION,
    MULTIVARIATE_SCIENTIFIC_STATUS,
)
from systems.models import ObservableDefinition, SystemRevision
from workspaces.permissions import can_edit_analysis, can_run_analysis

from .models import Analysis, AnalysisKind, AnalysisRun, AnalysisRunComponent, AnalysisStatus, RunStatus
from .multivariate_results import MULTIVARIATE_RESULT_SCHEMA_VERSION
from .multivariate_validation import (
    validate_multivariate_mapping,
    validate_multivariate_samples,
    validate_multivariate_units,
    resolve_multivariate_parameters,
)
from .services import (
    _enqueue,
    _fingerprint,
    _next_run_number,
    _record,
    _resolve_source,
    _source_snapshot,
    software_context,
)
from .sources import SourceContractError, descriptor_for, materialize_matrix


def _require_multivariate(analysis: Analysis) -> None:
    if analysis.analysis_kind != AnalysisKind.MULTIVARIATE:
        raise ValidationError(_("This workflow is only available for Multivariate Analyses."))


def _component_observables(*, project, revision, component_configs: list[dict]):
    ids = [str(item.get("observable_id") or "") for item in component_configs]
    if any(not value for value in ids):
        raise ValidationError(_("Every component must map to a System observable."))
    definitions = {
        str(item.pk): item
        for item in ObservableDefinition.objects.filter(
            pk__in=ids,
            revision=revision,
            revision__system__project=project,
        ).select_related("revision")
    }
    try:
        return [definitions[value] for value in ids]
    except KeyError as exc:
        raise ValidationError(
            _("Every selected observable must belong to the pinned System Revision.")
        ) from exc


@transaction.atomic
def configure_multivariate_analysis(
    *,
    actor,
    analysis: Analysis,
    coordinate_position: int,
    system_revision: SystemRevision,
    component_configs: list[dict],
    parameter_modes: dict,
    options: dict | None = None,
) -> Analysis:
    if not can_edit_analysis(actor, analysis):
        raise PermissionDenied
    locked = Analysis.objects.select_for_update().select_related("project").get(pk=analysis.pk)
    _require_multivariate(locked)
    if locked.status != AnalysisStatus.ACTIVE:
        raise ValidationError(_("Restore the Analysis before changing its configuration."))
    if system_revision.system.project_id != locked.project_id:
        raise ValidationError(_("The selected System Revision belongs to another Project."))

    descriptor = _resolve_source(locked, locked.draft_configuration)[2]
    positions = [int(item["source_position"]) for item in component_configs]
    coordinate, source_components = validate_multivariate_mapping(
        descriptor,
        coordinate_position=int(coordinate_position),
        component_positions=positions,
    )
    observables = _component_observables(
        project=locked.project,
        revision=system_revision,
        component_configs=component_configs,
    )
    resolved = resolve_multivariate_parameters(
        revision=system_revision,
        component_configs=component_configs,
        a_ref_mode=str(parameter_modes.get("A_ref") or ""),
        tau_mode=str(parameter_modes.get("tau") or ""),
        w_mode=str(parameter_modes.get("w") or ""),
        p_c_mode=str(parameter_modes.get("P_c") or ""),
    )
    unit_warnings = validate_multivariate_units(
        coordinate=coordinate,
        source_components=source_components,
        observable_definitions=observables,
        component_parameters=resolved["components"],
    )
    normalized_components = []
    for position, (source, observable, parameters) in enumerate(
        zip(source_components, observables, resolved["components"], strict=True),
        start=1,
    ):
        normalized_components.append(
            {
                "position": position,
                "source_position": int(source["position"]),
                "source_identity": str(source["identity"]),
                "observable_id": str(observable.pk),
                "parameters": parameters,
            }
        )
    selected_options = dict(options or {})
    locked.draft_configuration = {
        "source_type": descriptor.source_type,
        "source_id": descriptor.source_id,
        "coordinate_position": int(coordinate_position),
        "system_revision_id": str(system_revision.pk),
        "components": normalized_components,
        "parameter_modes": {
            "A_ref": resolved["call"]["A_ref"]["mode"],
            "tau": resolved["call"]["tau"]["mode"],
            "w": resolved["call"]["w"]["mode"],
            "P_c": resolved["call"]["P_c"]["mode"],
        },
        "call_contract": resolved["call"],
        "options": {
            "scientific_status": MULTIVARIATE_SCIENTIFIC_STATUS,
            "public_function": MULTIVARIATE_PUBLIC_FUNCTION,
            **{str(key): value for key, value in selected_options.items()},
        },
        "preflight_warnings": unit_warnings,
    }
    locked.save(update_fields=("draft_configuration", "updated_at"))
    _record(
        locked,
        actor=actor,
        event="ANALYSIS_UPDATED",
        detail=_("Updated multivariate Analysis configuration."),
    )
    return locked


def review_multivariate_snapshot(analysis: Analysis) -> dict:
    _require_multivariate(analysis)
    config = dict(analysis.draft_configuration or {})
    raw, prepared, descriptor = _resolve_source(analysis, config)
    revision = SystemRevision.objects.select_related("system").get(
        pk=config.get("system_revision_id"),
        system__project=analysis.project,
    )
    components_config = list(config.get("components") or [])
    positions = [int(item["source_position"]) for item in components_config]
    coordinate, source_components = validate_multivariate_mapping(
        descriptor,
        coordinate_position=int(config["coordinate_position"]),
        component_positions=positions,
    )
    observables = _component_observables(
        project=analysis.project,
        revision=revision,
        component_configs=components_config,
    )
    component_parameters = [deepcopy(item["parameters"]) for item in components_config]
    warnings = [*config.get("preflight_warnings", []), *descriptor.quality_issues]
    return {
        "descriptor": descriptor,
        "coordinate": coordinate,
        "source_components": source_components,
        "observables": observables,
        "components": [
            {
                "position": index,
                "source": source,
                "observable": observable,
                "parameters": parameters,
            }
            for index, (source, observable, parameters) in enumerate(
                zip(source_components, observables, component_parameters, strict=True),
                start=1,
            )
        ],
        "revision": revision,
        "call_contract": deepcopy(config.get("call_contract") or {}),
        "options": deepcopy(config.get("options") or {}),
        "warnings": warnings,
        "raw": raw,
        "prepared": prepared,
    }


def _mapping_snapshot(snapshot: dict) -> dict:
    return {
        "time": {**snapshot["coordinate"]},
        "components": [
            {
                "position": item["position"],
                **item["source"],
                "system_observable_id": str(item["observable"].pk),
                "system_observable_name": item["observable"].name,
                "system_observable_symbol": item["observable"].symbol,
            }
            for item in snapshot["components"]
        ],
    }


@transaction.atomic
def queue_multivariate_run(*, actor, analysis: Analysis) -> AnalysisRun:
    if not can_run_analysis(actor, analysis):
        raise PermissionDenied
    locked = Analysis.objects.select_for_update().select_related("project").get(pk=analysis.pk)
    _require_multivariate(locked)
    if locked.status != AnalysisStatus.ACTIVE:
        raise ValidationError(_("Restore the Analysis before running it."))
    snapshot = review_multivariate_snapshot(locked)
    raw, prepared = snapshot["raw"], snapshot["prepared"]
    xi, matrix = materialize_matrix(
        dataset_version=raw,
        prepared_artifact=prepared,
        coordinate_position=int(snapshot["coordinate"]["position"]),
        component_positions=[item["source"]["position"] for item in snapshot["components"]],
    )
    validate_multivariate_samples(
        xi,
        matrix,
        component_parameters=[item["parameters"] for item in snapshot["components"]],
    )
    context = software_context()
    if context["agencitylab_version"] != "1.1.3":
        raise ValidationError(_("AgencityLab 1.1.3 is required for this Analysis contract."))
    mapping = _mapping_snapshot(snapshot)
    source_snapshot = _source_snapshot(snapshot["descriptor"])
    component_fingerprint_payload = [
        {
            "position": item["position"],
            "source_identity": item["source"]["identity"],
            "source_position": item["source"]["position"],
            "observable_id": str(item["observable"].pk),
            "parameters": item["parameters"],
        }
        for item in snapshot["components"]
    ]
    execution_payload = {
        "analysis_kind": AnalysisKind.MULTIVARIATE,
        "source_sha256": snapshot["descriptor"].sha256,
        "source_type": snapshot["descriptor"].source_type,
        "coordinate": mapping["time"],
        "ordered_components": component_fingerprint_payload,
        "call_contract": snapshot["call_contract"],
        "system_revision_id": str(snapshot["revision"].pk),
        "system_configuration_fingerprint": snapshot["revision"].configuration_fingerprint,
        "options": snapshot["options"],
        "agencitylab_version": context["agencitylab_version"],
        "result_schema_version": MULTIVARIATE_RESULT_SCHEMA_VERSION,
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
        system_observable=None,
        system_configuration_fingerprint=snapshot["revision"].configuration_fingerprint,
        parameter_snapshot={
            "call_contract": snapshot["call_contract"],
            "component_count": len(snapshot["components"]),
        },
        analysis_options=snapshot["options"],
        agencitylab_version=context["agencitylab_version"],
        studio_version=context["studio_version"],
        python_version=context["python_version"],
        execution_fingerprint=_fingerprint(execution_payload),
        warnings=list(snapshot["warnings"]),
        created_by=actor,
        queued_at=timezone.now(),
    )
    AnalysisRunComponent.objects.bulk_create(
        [
            AnalysisRunComponent(
                run=run,
                position=item["position"],
                observable_definition=item["observable"],
                source_column_identity=str(item["source"]["identity"]),
                source_column_position=int(item["source"]["position"]),
                source_name=str(item["source"].get("source_name") or ""),
                display_name=str(item["source"].get("display_name") or ""),
                unit=str(item["source"].get("unit") or ""),
                parameter_snapshot=deepcopy(item["parameters"]),
            )
            for item in snapshot["components"]
        ]
    )
    _record(
        locked,
        actor=actor,
        event="ANALYSIS_RUN_QUEUED",
        detail=_("Queued multivariate Analysis Run %(number)s.") % {"number": run.run_number},
    )
    transaction.on_commit(lambda: _enqueue(run.pk))
    return run


@transaction.atomic
def rerun_multivariate_run(*, actor, run: AnalysisRun) -> AnalysisRun:
    analysis = Analysis.objects.select_for_update().select_related("project").get(pk=run.analysis_id)
    _require_multivariate(analysis)
    if not can_run_analysis(actor, analysis):
        raise PermissionDenied
    source_run = (
        AnalysisRun.objects.select_related(
            "source_dataset_version",
            "source_prepared_artifact",
            "system_revision",
        )
        .prefetch_related("components__observable_definition")
        .get(pk=run.pk, analysis=analysis)
    )
    raw = source_run.source_dataset_version
    prepared = source_run.source_prepared_artifact
    descriptor = descriptor_for(dataset_version=raw) if raw else descriptor_for(prepared_artifact=prepared)
    if descriptor.sha256 != source_run.source_sha256:
        raise ValidationError(_("The pinned source hash no longer matches the historical Run."))
    components = list(source_run.components.order_by("position"))
    xi, matrix = materialize_matrix(
        dataset_version=raw,
        prepared_artifact=prepared,
        coordinate_position=int(source_run.mapping_snapshot["time"]["position"]),
        component_positions=[item.source_column_position for item in components],
    )
    validate_multivariate_samples(
        xi,
        matrix,
        component_parameters=[item.parameter_snapshot for item in components],
    )
    context = software_context()
    if context["agencitylab_version"] != source_run.agencitylab_version:
        raise ValidationError(
            _("Exact rerun requires the same AgencityLab version as the historical Run.")
        )
    rerun = AnalysisRun.objects.create(
        analysis=analysis,
        run_number=_next_run_number(analysis),
        status=RunStatus.QUEUED,
        source_type=source_run.source_type,
        source_dataset_version=raw,
        source_prepared_artifact=prepared,
        source_sha256=source_run.source_sha256,
        source_snapshot=source_run.source_snapshot,
        mapping_snapshot=source_run.mapping_snapshot,
        system_revision=source_run.system_revision,
        system_observable=None,
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
    AnalysisRunComponent.objects.bulk_create(
        [
            AnalysisRunComponent(
                run=rerun,
                position=item.position,
                observable_definition=item.observable_definition,
                source_column_identity=item.source_column_identity,
                source_column_position=item.source_column_position,
                source_name=item.source_name,
                display_name=item.display_name,
                unit=item.unit,
                parameter_snapshot=deepcopy(item.parameter_snapshot),
            )
            for item in components
        ]
    )
    _record(
        analysis,
        actor=actor,
        event="ANALYSIS_RUN_QUEUED",
        detail=_("Queued exact multivariate rerun %(number)s from Run %(source)s.")
        % {"number": rerun.run_number, "source": source_run.run_number},
    )
    transaction.on_commit(lambda: _enqueue(rerun.pk))
    return rerun
