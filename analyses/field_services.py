"""Configuration, review and immutable Run services for observable spatial fields."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from datasets.field_source import field_inventory, is_field_source
from datasets.models import DatasetImportStatus, DatasetVersion
from labbridge.service import SUPPORTED_AGENCITYLAB_VERSION
from projects.models import ProjectActivity
from systems.models import MemoryWindowMode, ObservableDefinition, SystemRevision
from workspaces.permissions import can_edit_analysis, can_run_analysis

from .field_contract import (
    FIELD_ANALYSIS_KIND,
    FIELD_PUBLIC_FUNCTION,
    FIELD_RESULT_SCHEMA_VERSION,
    FIELD_SCIENTIFIC_STATUS,
    PARAMETER_MODE_SCALAR,
    PARAMETER_MODE_SPATIAL,
    POWER_MODE_SPACETIME,
    SPATIAL_AXES_EXPLICIT,
    WINDOW_MODE_UNSPECIFIED,
)
from .field_validation import validate_geometry, validate_parameter_modes
from .models import Analysis, AnalysisRun, AnalysisStatus, RunStatus, SourceType
from .services import _enqueue, _fingerprint, _next_run_number, software_context


def _record(analysis, actor, event: str, detail: str) -> None:
    ProjectActivity.objects.create(
        project=analysis.project,
        actor=actor,
        event=event,
        detail=detail[:255],
    )


def _source(analysis: Analysis) -> DatasetVersion:
    config = dict(analysis.draft_configuration or {})
    try:
        version = DatasetVersion.objects.select_related("dataset", "dataset__project").get(
            pk=config.get("source_id"), dataset__project=analysis.project
        )
    except (DatasetVersion.DoesNotExist, ValueError) as exc:
        raise ValidationError(_("The field Analysis no longer identifies a valid Dataset Version.")) from exc
    if version.import_status != DatasetImportStatus.READY or not is_field_source(version):
        raise ValidationError(_("The pinned Dataset Version is not a ready observable field source."))
    return version


def _system_scalar_snapshot(revision: SystemRevision, name: str) -> dict:
    prefix = {"A_ref": "a_ref", "P_c": "p_c"}.get(name, name)
    value = getattr(revision, f"{prefix}_value")
    if value is None:
        raise ValidationError(
            _("%(name)s scalar mode requires an explicit value in the selected System Revision.")
            % {"name": name}
        )
    numeric = float(value)
    if name in {"A_ref", "tau", "w"} and numeric <= 0:
        raise ValidationError(_("%(name)s must be strictly positive.") % {"name": name})
    if name == "P_c" and numeric < 0:
        raise ValidationError(_("P_c must be non-negative; P_c = 0 is valid."))
    return {
        "mode": PARAMETER_MODE_SCALAR,
        "value": numeric,
        "value_text": getattr(revision, f"{prefix}_value_text"),
        "unit": getattr(revision, f"{prefix}_unit"),
        "origin": getattr(revision, f"{prefix}_origin"),
        "origin_detail": getattr(revision, f"{prefix}_origin_detail"),
        "justification": getattr(revision, f"{prefix}_justification"),
        "source": "SYSTEM_REVISION_SCALAR",
    }


def _map_snapshot(*, name: str, descriptor: dict, unit: str, provenance: str, actor) -> dict:
    return {
        "mode": PARAMETER_MODE_SPATIAL,
        "array_key": descriptor["key"],
        "shape": descriptor["shape"],
        "dtype": descriptor["dtype"],
        "npy_sha256": descriptor["npy_sha256"],
        "unit": unit,
        "provenance": str(provenance).strip(),
        "supplied_by_user_id": str(actor.pk),
        "source": "PINNED_FIELD_SOURCE_ARRAY",
        "parameter": name,
    }


def _parameter_snapshots(*, revision, config: dict, descriptors: dict, actor) -> dict:
    snapshots: dict[str, dict] = {}
    for name, unit in (("A_ref", revision.a_ref_unit), ("tau", revision.tau_unit)):
        if config[f"{name}_mode"] == PARAMETER_MODE_SCALAR:
            snapshots[name] = _system_scalar_snapshot(revision, name)
        else:
            snapshots[name] = _map_snapshot(
                name=name,
                descriptor=descriptors[name],
                unit=unit,
                provenance=config.get(f"{name}_map_provenance", ""),
                actor=actor,
            )

    if config["w_mode"] == WINDOW_MODE_UNSPECIFIED:
        snapshots["w"] = {
            "mode": WINDOW_MODE_UNSPECIFIED,
            "requested_value": None,
            "unit": revision.w_unit or revision.tau_unit,
            "origin": revision.w_origin,
            "origin_detail": revision.w_origin_detail,
            "justification": revision.w_justification,
            "source": "UNSPECIFIED_PUBLIC_API_REQUEST",
        }
    elif config["w_mode"] == PARAMETER_MODE_SCALAR:
        if revision.w_mode != MemoryWindowMode.EXPLICIT:
            raise ValidationError(
                _("Scalar w mode requires an explicit w in the selected System Revision. Use Unspecified (w=None) otherwise.")
            )
        snapshots["w"] = _system_scalar_snapshot(revision, "w")
        snapshots["w"]["requested_value"] = snapshots["w"]["value"]
    else:
        snapshots["w"] = _map_snapshot(
            name="w",
            descriptor=descriptors["w"],
            unit=revision.w_unit or revision.tau_unit,
            provenance=config.get("w_map_provenance", ""),
            actor=actor,
        )

    if config["P_c_mode"] == PARAMETER_MODE_SCALAR:
        snapshots["P_c"] = _system_scalar_snapshot(revision, "P_c")
    else:
        snapshots["P_c"] = _map_snapshot(
            name="P_c",
            descriptor=descriptors["P_c"],
            unit=revision.p_c_unit,
            provenance=config.get("P_c_map_provenance", ""),
            actor=actor,
        )
        snapshots["P_c"]["mode"] = config["P_c_mode"]
    return snapshots


def _axis_metadata(config: dict, geometry) -> list[dict]:
    count = len(geometry.spatial_shape)
    names = list(config.get("spatial_axis_names") or [])
    units = list(config.get("spatial_axis_units") or [])
    keys = list(config.get("spatial_axis_keys") or [])
    while len(names) < count:
        names.append(f"spatial_index_{len(names) + 1}")
    while len(units) < count:
        units.append("")
    axes = []
    for index, length in enumerate(geometry.spatial_shape):
        descriptor = geometry.spatial_axis_descriptors[index]
        axes.append(
            {
                "dimension": index,
                "name": names[index] or f"spatial_index_{index + 1}",
                "unit": units[index],
                "length": int(length),
                "mode": config["spatial_axes_mode"],
                "array_key": keys[index] if descriptor is not None else None,
                "array": dict(descriptor) if descriptor is not None else None,
            }
        )
    return axes


def _review(analysis: Analysis, *, actor=None) -> dict:
    if analysis.analysis_kind != FIELD_ANALYSIS_KIND:
        raise ValidationError(_("This Analysis is not an observable spatial field Analysis."))
    config = dict(analysis.draft_configuration or {})
    if not config.get("configured"):
        raise ValidationError(_("Complete the field configuration before Review."))
    version = _source(analysis)
    try:
        revision = SystemRevision.objects.select_related("system").get(
            pk=config["system_revision_id"], system__project=analysis.project
        )
        observable = ObservableDefinition.objects.get(
            pk=config["system_observable_id"], revision=revision
        )
    except (KeyError, SystemRevision.DoesNotExist, ObservableDefinition.DoesNotExist) as exc:
        raise ValidationError(_("The configured System Revision or observable is unavailable.")) from exc
    geometry = validate_geometry(
        version=version,
        u_key=config["u_key"],
        t_key=config["t_key"],
        time_axis=config["time_axis"],
        spatial_axes_mode=config["spatial_axes_mode"],
        spatial_axis_keys=list(config.get("spatial_axis_keys") or []),
    )
    descriptors = validate_parameter_modes(version=version, geometry=geometry, config=config)
    source_observable_unit = str(config.get("observable_unit", "")).strip()
    if source_observable_unit and observable.unit and source_observable_unit != observable.unit:
        raise ValidationError(
            _("Observable unit does not match the selected System observable. Studio does not convert field values during Analysis.")
        )
    time_unit = str(config.get("time_unit", "")).strip()
    if time_unit and revision.tau_unit and time_unit != revision.tau_unit:
        raise ValidationError(
            _("Time unit does not match the selected System tau unit. Prepare or document matching units before Analysis.")
        )
    parameter_actor = actor or analysis.created_by
    parameters = _parameter_snapshots(
        revision=revision,
        config=config,
        descriptors=descriptors,
        actor=parameter_actor,
    )
    axes = _axis_metadata(config, geometry)
    u_descriptor = next(item for item in field_inventory(version) if item["key"] == config["u_key"])
    t_descriptor = next(item for item in field_inventory(version) if item["key"] == config["t_key"])
    mapping = {
        "u": {**u_descriptor, "unit": source_observable_unit, "observable_id": str(observable.pk), "observable_name": observable.name},
        "time": {**t_descriptor, "unit": time_unit, "time_axis": geometry.time_axis},
        "field_shape": list(geometry.field_shape),
        "spatial_shape": list(geometry.spatial_shape),
        "spatial_axes_mode": config["spatial_axes_mode"],
        "spatial_axes": axes,
        "axis_order_significant": True,
    }
    warnings = []
    if config["spatial_axes_mode"] != SPATIAL_AXES_EXPLICIT:
        warnings.append(
            {
                "category": "SPATIAL_INDEX_COORDINATES",
                "message": "No physical spatial coordinate arrays were supplied; Lab spatial_axes=None sample indices are preserved.",
            }
        )
    return {
        "version": version,
        "revision": revision,
        "observable": observable,
        "geometry": geometry,
        "mapping": mapping,
        "parameters": parameters,
        "config": config,
        "warnings": warnings,
    }


@transaction.atomic
def configure_observable_field_analysis(*, actor, analysis: Analysis, values: dict) -> Analysis:
    if not can_edit_analysis(actor, analysis):
        raise PermissionDenied
    locked = Analysis.objects.select_for_update().select_related("project").get(pk=analysis.pk)
    if locked.analysis_kind != FIELD_ANALYSIS_KIND:
        raise ValidationError(_("This Analysis is not an observable spatial field Analysis."))
    if locked.status != AnalysisStatus.ACTIVE:
        raise ValidationError(_("Restore the Analysis before changing its configuration."))
    revision = values["system_revision"]
    observable = values["system_observable"]
    if revision.system.project_id != locked.project_id or observable.revision_id != revision.pk:
        raise ValidationError(_("The selected System context does not belong to this Project and revision."))
    source_id = locked.draft_configuration.get("source_id")
    config = {
        "source_type": SourceType.RAW_DATASET_VERSION,
        "source_id": str(source_id),
        "scientific_status": FIELD_SCIENTIFIC_STATUS,
        "configured": True,
        "u_key": values["u_key"],
        "t_key": values["t_key"],
        "time_axis": int(values["time_axis"]),
        "time_unit": str(values.get("time_unit", "")).strip(),
        "observable_unit": str(values.get("observable_unit", "")).strip(),
        "spatial_axes_mode": values["spatial_axes_mode"],
        "spatial_axis_keys": list(values.get("spatial_axis_keys") or []),
        "spatial_axis_names": list(values.get("spatial_axis_names") or []),
        "spatial_axis_units": list(values.get("spatial_axis_units") or []),
        "system_revision_id": str(revision.pk),
        "system_observable_id": str(observable.pk),
        "A_ref_mode": values["A_ref_mode"],
        "A_ref_map_key": values.get("A_ref_map_key", ""),
        "A_ref_map_provenance": str(values.get("A_ref_map_provenance", "")).strip(),
        "tau_mode": values["tau_mode"],
        "tau_map_key": values.get("tau_map_key", ""),
        "tau_map_provenance": str(values.get("tau_map_provenance", "")).strip(),
        "w_mode": values["w_mode"],
        "w_map_key": values.get("w_map_key", ""),
        "w_map_provenance": str(values.get("w_map_provenance", "")).strip(),
        "P_c_mode": values["P_c_mode"],
        "P_c_map_key": values.get("P_c_map_key", ""),
        "P_c_map_provenance": str(values.get("P_c_map_provenance", "")).strip(),
        "field_description": str(values.get("field_description", "")).strip(),
    }
    locked.draft_configuration = config
    locked.save(update_fields=("draft_configuration", "updated_at"))
    _review(locked, actor=actor)
    _record(locked, actor, "ANALYSIS_UPDATED", _("Updated EXPERIMENTAL observable field configuration."))
    return locked


def observable_field_review_snapshot(analysis: Analysis) -> dict:
    return _review(analysis)


def _source_snapshot(version: DatasetVersion) -> dict:
    return {
        "type": SourceType.RAW_DATASET_VERSION,
        "id": str(version.pk),
        "dataset_id": str(version.dataset_id),
        "filename": version.original_filename,
        "size_bytes": version.source_size_bytes,
        "sha256": version.source_sha256,
        "format": version.source_format,
        "array_inventory": field_inventory(version),
        "lineage": [
            {
                "kind": "RAW_DATASET_VERSION",
                "dataset_id": str(version.dataset_id),
                "version_id": str(version.pk),
                "sha256": version.source_sha256,
            }
        ],
    }


@transaction.atomic
def queue_observable_field_run(*, actor, analysis: Analysis) -> AnalysisRun:
    if not can_run_analysis(actor, analysis):
        raise PermissionDenied
    locked = Analysis.objects.select_for_update().select_related("project").get(pk=analysis.pk)
    if locked.status != AnalysisStatus.ACTIVE:
        raise ValidationError(_("Restore the Analysis before running it."))
    snapshot = _review(locked, actor=actor)
    context = software_context()
    if context["agencitylab_version"] != SUPPORTED_AGENCITYLAB_VERSION:
        raise ValidationError(
            _("AgencityLab %(version)s is required for this field Analysis contract.")
            % {"version": SUPPORTED_AGENCITYLAB_VERSION}
        )
    source_snapshot = _source_snapshot(snapshot["version"])
    options = {
        "public_function": FIELD_PUBLIC_FUNCTION,
        "scientific_status": FIELD_SCIENTIFIC_STATUS,
        "model": "observable_agencity_field",
        "crm_scope": "temporal_only_independent_at_each_spatial_location",
        "field_description": snapshot["config"].get("field_description", ""),
    }
    payload = {
        "source_sha256": snapshot["version"].source_sha256,
        "field_shape": snapshot["mapping"]["field_shape"],
        "time_axis": snapshot["mapping"]["time"]["time_axis"],
        "mapping": snapshot["mapping"],
        "parameters": snapshot["parameters"],
        "system_revision_id": str(snapshot["revision"].pk),
        "system_configuration_fingerprint": snapshot["revision"].configuration_fingerprint,
        "agencitylab_version": context["agencitylab_version"],
        "result_schema_version": FIELD_RESULT_SCHEMA_VERSION,
        "scientific_status": FIELD_SCIENTIFIC_STATUS,
    }
    run = AnalysisRun.objects.create(
        analysis=locked,
        run_number=_next_run_number(locked),
        status=RunStatus.QUEUED,
        source_type=SourceType.RAW_DATASET_VERSION,
        source_dataset_version=snapshot["version"],
        source_prepared_artifact=None,
        source_sha256=snapshot["version"].source_sha256,
        source_snapshot=source_snapshot,
        mapping_snapshot=snapshot["mapping"],
        system_revision=snapshot["revision"],
        system_observable=snapshot["observable"],
        system_configuration_fingerprint=snapshot["revision"].configuration_fingerprint,
        parameter_snapshot=snapshot["parameters"],
        analysis_options=options,
        agencitylab_version=context["agencitylab_version"],
        studio_version=context["studio_version"],
        python_version=context["python_version"],
        execution_fingerprint=_fingerprint(payload),
        warnings=list(snapshot["warnings"]),
        created_by=actor,
        queued_at=timezone.now(),
    )
    _record(
        locked,
        actor,
        "ANALYSIS_RUN_QUEUED",
        _("Queued EXPERIMENTAL observable field Run %(number)s.") % {"number": run.run_number},
    )
    transaction.on_commit(lambda: _enqueue(run.pk))
    return run


@transaction.atomic
def rerun_observable_field(*, actor, run: AnalysisRun) -> AnalysisRun:
    analysis = Analysis.objects.select_for_update().select_related("project").get(pk=run.analysis_id)
    if not can_run_analysis(actor, analysis):
        raise PermissionDenied
    if analysis.status != AnalysisStatus.ACTIVE:
        raise ValidationError(_("Restore the Analysis before running it again."))
    source_run = AnalysisRun.objects.select_related(
        "source_dataset_version", "system_revision", "system_observable"
    ).get(pk=run.pk, analysis=analysis)
    if source_run.analysis.analysis_kind != FIELD_ANALYSIS_KIND:
        raise ValidationError(_("This historical Run is not an observable field Run."))
    version = source_run.source_dataset_version
    if not version or version.source_sha256 != source_run.source_sha256 or not is_field_source(version):
        raise ValidationError(_("The pinned field source no longer matches the historical Run."))
    context = software_context()
    if context["agencitylab_version"] != source_run.agencitylab_version:
        raise ValidationError(_("Exact rerun requires the same AgencityLab version."))
    rerun = AnalysisRun.objects.create(
        analysis=analysis,
        run_number=_next_run_number(analysis),
        status=RunStatus.QUEUED,
        source_type=source_run.source_type,
        source_dataset_version=version,
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
        analysis,
        actor,
        "ANALYSIS_RUN_QUEUED",
        _("Queued exact observable field rerun %(number)s from Run %(source)s.")
        % {"number": rerun.run_number, "source": source_run.run_number},
    )
    transaction.on_commit(lambda: _enqueue(rerun.pk))
    return rerun