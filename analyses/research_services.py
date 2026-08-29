"""Configuration, Review and immutable Run services for autonomous RESEARCH fields."""

from __future__ import annotations

import hashlib
import uuid

import numpy as np
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from datasets.field_source import FieldSourceError, is_field_source, load_npz_arrays
from datasets.models import DatasetVersion
from labbridge.research import (
    ResearchLabError,
    bridge_beta_to_phi,
    domain_wall_initial_field,
    make_generated_grid,
    make_grid,
    vortex_initial_field,
)
from projects.models import ProjectActivity
from workspaces.permissions import can_create_analysis, can_edit_analysis, can_run_analysis

from .field_storage import open_observable_field_result_reader
from .models import (
    Analysis,
    AnalysisKind,
    AnalysisRun,
    AnalysisStatus,
    ResearchFieldInputArtifact,
    RunStatus,
    SourceType,
)
from .research_capabilities import research_capabilities
from .research_contract import (
    BETA_PHI_BOUNDARY,
    INITIAL_DOMAIN_WALL,
    INITIAL_NPZ,
    INITIAL_OBSERVABLE_BRIDGE,
    INITIAL_VORTEX_PROFILE,
    MODEL_TDGL,
    PUBLIC_APIS,
    RESEARCH_ANALYSIS_KIND,
    RESEARCH_SCIENTIFIC_STATUS,
    SCIENTIFIC_DISCLAIMER,
)
from .research_results import serialize_research_input
from .research_storage import write_research_input
from .services import _enqueue, _fingerprint, _next_run_number, software_context
from .storage import analysis_storage


class ResearchConfigurationError(ValueError):
    """Raised when Studio cannot freeze a valid public-Lab Research configuration."""


def _record(analysis, actor, event: str, detail: str) -> None:
    ProjectActivity.objects.create(
        project=analysis.project,
        actor=actor,
        event=event,
        detail=detail[:255],
    )


@transaction.atomic
def create_research_field_analysis(*, actor, project, name: str, description: str = "") -> Analysis:
    if not can_create_analysis(actor, project):
        raise PermissionDenied
    clean_name = str(name).strip()
    if not clean_name:
        raise ValidationError(_("Analysis name is required."))
    analysis = Analysis.objects.create(
        project=project,
        name=clean_name,
        description=str(description).strip(),
        analysis_kind=AnalysisKind.RESEARCH_FIELD,
        created_by=actor,
        draft_configuration={
            "scientific_status": RESEARCH_SCIENTIFIC_STATUS,
            "configured": False,
        },
    )
    _record(
        analysis,
        actor,
        "ANALYSIS_CREATED",
        _("Created RESEARCH autonomous field Analysis %(name)s.") % {"name": analysis.name},
    )
    return analysis


def _json_configuration(values: dict) -> dict:
    source = values.get("source")
    observable_run = values.get("observable_run")
    return {
        "scientific_status": RESEARCH_SCIENTIFIC_STATUS,
        "configured": True,
        "model": values["model"],
        "initial_mode": values["initial_mode"],
        "initial_velocity_mode": values["initial_velocity_mode"],
        "source_id": str(source.pk) if source else None,
        "phi_key": str(values.get("phi_key") or "").strip(),
        "phi_dot_key": str(values.get("phi_dot_key") or "").strip(),
        "spatial_axis_keys": list(values.get("spatial_axis_keys_parsed") or []),
        "observable_run_id": str(observable_run.pk) if observable_run else None,
        "observable_time_index": values.get("observable_time_index"),
        "generated_shape": list(values.get("generated_shape_parsed") or []),
        "generated_spacings": list(values.get("generated_spacings_parsed") or []),
        "generated_origins": list(values.get("generated_origins_parsed") or []),
        "domain_wall_center": values.get("domain_wall_center"),
        "domain_wall_orientation": int(values.get("domain_wall_orientation") or 1),
        "vortex_winding": values.get("vortex_winding"),
        "radial_profile_key": str(values.get("radial_profile_key") or "").strip(),
        "vortex_x_key": str(values.get("vortex_x_key") or "").strip(),
        "vortex_y_key": str(values.get("vortex_y_key") or "").strip(),
        "lambda": float(values["lambda_"]),
        "lambda_origin": str(values["lambda_origin"]).strip(),
        "mu": float(values["mu"]),
        "mu_origin": str(values["mu_origin"]).strip(),
        "gamma": None if values.get("gamma") is None else float(values["gamma"]),
        "gamma_origin": str(values.get("gamma_origin") or "").strip(),
        "units_convention": values["units_convention"],
        "boundary_kind": values["boundary_kind"],
        "boundary_value": {
            "real": float(values.get("boundary_value_real") or 0.0),
            "imag": float(values.get("boundary_value_imag") or 0.0),
        },
        "dt_solver": float(values["dt_solver"]),
        "n_steps": int(values["n_steps"]),
        "topology_contour_indices": list(values.get("topology_contour_indices_parsed") or []),
        "thermo_t_eff": None if values.get("thermo_t_eff") is None else float(values["thermo_t_eff"]),
        "thermo_entropy_a": (
            None if values.get("thermo_entropy_a") is None else float(values["thermo_entropy_a"])
        ),
    }


@transaction.atomic
def configure_research_field_analysis(*, actor, analysis: Analysis, values: dict) -> Analysis:
    if not can_edit_analysis(actor, analysis):
        raise PermissionDenied
    locked = Analysis.objects.select_for_update().select_related("project").get(pk=analysis.pk)
    if locked.analysis_kind != RESEARCH_ANALYSIS_KIND:
        raise ValidationError(_("This Analysis is not a RESEARCH autonomous field Analysis."))
    if locked.status != AnalysisStatus.ACTIVE:
        raise ValidationError(_("Restore the Analysis before changing its configuration."))
    locked.draft_configuration = _json_configuration(values)
    locked.save(update_fields=("draft_configuration", "updated_at"))
    research_field_review_snapshot(locked)
    _record(locked, actor, "ANALYSIS_UPDATED", _("Updated RESEARCH field configuration."))
    return locked


def _dataset_for(analysis: Analysis, source_id: str | None) -> DatasetVersion:
    if not source_id:
        raise ResearchConfigurationError("A pinned NPZ Dataset Version is required.")
    try:
        version = DatasetVersion.objects.select_related("dataset").get(
            pk=source_id,
            dataset__project=analysis.project,
            dataset__current_version_id=source_id,
        )
    except (DatasetVersion.DoesNotExist, ValueError) as exc:
        raise ResearchConfigurationError("The pinned NPZ source is unavailable in this Project.") from exc
    if not is_field_source(version):
        raise ResearchConfigurationError("The pinned source is not an inspected immutable NPZ field source.")
    return version


def _zero_velocity(phi0):
    return np.zeros_like(np.asarray(phi0))


def _npz_initial(analysis: Analysis, config: dict):
    version = _dataset_for(analysis, config.get("source_id"))
    keys = [config["phi_key"], *config.get("spatial_axis_keys", [])]
    if config.get("initial_velocity_mode") == "NPZ_ARRAY":
        keys.append(config["phi_dot_key"])
    arrays = load_npz_arrays(version, keys)
    phi0 = np.asarray(arrays[config["phi_key"]])
    axes = tuple(np.asarray(arrays[key]) for key in config["spatial_axis_keys"])
    grid = make_grid(axes=axes)
    if phi0.shape != grid.shape:
        raise ResearchConfigurationError(
            f"Initial phi shape {phi0.shape} does not match grid shape {grid.shape}."
        )
    phi_dot0 = None
    if config.get("initial_velocity_mode") == "NPZ_ARRAY":
        phi_dot0 = np.asarray(arrays[config["phi_dot_key"]])
        if phi_dot0.shape != phi0.shape:
            raise ResearchConfigurationError("Initial phi_dot must have exactly the phi shape.")
    source = {
        "kind": "PINNED_NPZ_ARRAY",
        "dataset_version_id": str(version.pk),
        "source_sha256": version.source_sha256,
        "phi_key": config["phi_key"],
        "phi_dot_key": config.get("phi_dot_key") or None,
        "spatial_axis_keys": list(config["spatial_axis_keys"]),
    }
    return phi0, phi_dot0, tuple(grid.axes), source


def _observable_bridge_initial(analysis: Analysis, config: dict):
    try:
        source_run = AnalysisRun.objects.select_related("analysis").get(
            pk=config.get("observable_run_id"),
            analysis__project=analysis.project,
            analysis__analysis_kind=AnalysisKind.OBSERVABLE_SPATIAL_FIELD,
            status=RunStatus.COMPLETED,
        )
    except (AnalysisRun.DoesNotExist, ValueError) as exc:
        raise ResearchConfigurationError("The selected Observable Field Run is unavailable.") from exc
    if not hasattr(source_run, "result_artifact"):
        raise ResearchConfigurationError("The selected Observable Field Run has no immutable result artifact.")
    with open_observable_field_result_reader(source_run, verify_hash=True) as reader:
        manifest = reader.read_manifest()
        beta = reader.read_series("beta")
        power = reader.read_series("P_c")
        tau = reader.read_series("tau")
        time_axis = int(manifest["time_axis"])
        phi_spacetime = bridge_beta_to_phi(
            beta=beta,
            P_c=power,
            tau=tau,
            time_axis=time_axis,
        )
        time_index = int(config["observable_time_index"])
        if time_index < 0 or time_index >= phi_spacetime.shape[time_axis]:
            raise ResearchConfigurationError("The selected Observable Field time index is out of bounds.")
        phi0 = np.take(phi_spacetime, time_index, axis=time_axis)
        axes = tuple(
            reader.read_series(f"spatial_axis_{index}")
            for index in range(len(manifest["spatial_shape"]))
        )
    grid = make_grid(axes=axes)
    if phi0.shape != grid.shape:
        raise ResearchConfigurationError("Bridged phi spatial shape does not match the stored spatial grid.")
    source = {
        "kind": "EXPLICIT_OBSERVABLE_TO_PHI_BRIDGE",
        "source_run_id": str(source_run.pk),
        "source_result_sha256": source_run.result_sha256,
        "source_scientific_status": "EXPERIMENTAL",
        "public_function": PUBLIC_APIS["bridge"],
        "time_index": time_index,
        "time_axis": time_axis,
        "boundary_statement": BETA_PHI_BOUNDARY,
    }
    return np.asarray(phi0), None, tuple(grid.axes), source


def _domain_wall_initial(config: dict):
    grid = make_generated_grid(
        shape=config["generated_shape"],
        spacings=config["generated_spacings"],
        origins=config["generated_origins"],
    )
    if len(grid.shape) != 1:
        raise ResearchConfigurationError("The public domain-wall reference requires a one-dimensional grid.")
    phi0 = domain_wall_initial_field(
        x=grid.axes[0],
        lambda_=config["lambda"],
        mu=config["mu"],
        center=config["domain_wall_center"],
        orientation=config["domain_wall_orientation"],
    )
    source = {
        "kind": "AGENCITYLAB_DOMAIN_WALL_REFERENCE",
        "public_function": PUBLIC_APIS["domain_wall"],
        "center": config["domain_wall_center"],
        "orientation": config["domain_wall_orientation"],
        "note": "Real-sector/Z2 reference initialization; not automatic defect detection.",
    }
    return np.asarray(phi0), None, tuple(grid.axes), source


def _vortex_initial(analysis: Analysis, config: dict):
    version = _dataset_for(analysis, config.get("source_id"))
    keys = [config["vortex_x_key"], config["vortex_y_key"], config["radial_profile_key"]]
    if config.get("initial_velocity_mode") == "NPZ_ARRAY":
        keys.append(config["phi_dot_key"])
    arrays = load_npz_arrays(version, keys)
    x = np.asarray(arrays[config["vortex_x_key"]])
    y = np.asarray(arrays[config["vortex_y_key"]])
    grid = make_grid(axes=(x, y))
    profile = np.asarray(arrays[config["radial_profile_key"]])
    if profile.shape != grid.shape:
        raise ResearchConfigurationError(
            "The supplied vortex radial-profile array must match the exact x/y grid shape."
        )
    phi0 = vortex_initial_field(
        x=grid.axes[0],
        y=grid.axes[1],
        radial_profile=profile,
        winding=config["vortex_winding"],
        lambda_=config["lambda"],
        mu=config["mu"],
    )
    phi_dot0 = None
    if config.get("initial_velocity_mode") == "NPZ_ARRAY":
        phi_dot0 = np.asarray(arrays[config["phi_dot_key"]])
        if phi_dot0.shape != phi0.shape:
            raise ResearchConfigurationError("Initial phi_dot must have exactly the vortex phi shape.")
    source = {
        "kind": "AGENCITYLAB_VORTEX_FROM_SUPPLIED_PROFILE",
        "dataset_version_id": str(version.pk),
        "source_sha256": version.source_sha256,
        "public_function": PUBLIC_APIS["vortex"],
        "radial_profile_key": config["radial_profile_key"],
        "x_key": config["vortex_x_key"],
        "y_key": config["vortex_y_key"],
        "winding": config["vortex_winding"],
        "phi_dot_key": config.get("phi_dot_key") or None,
        "note": "The radial profile is user supplied; Studio does not invent a vortex profile formula.",
    }
    return np.asarray(phi0), phi_dot0, tuple(grid.axes), source


def _materialize_initial(analysis: Analysis, config: dict):
    mode = config["initial_mode"]
    if mode == INITIAL_NPZ:
        phi0, phi_dot0, axes, source = _npz_initial(analysis, config)
    elif mode == INITIAL_OBSERVABLE_BRIDGE:
        phi0, phi_dot0, axes, source = _observable_bridge_initial(analysis, config)
    elif mode == INITIAL_DOMAIN_WALL:
        phi0, phi_dot0, axes, source = _domain_wall_initial(config)
    elif mode == INITIAL_VORTEX_PROFILE:
        phi0, phi_dot0, axes, source = _vortex_initial(analysis, config)
    else:
        raise ResearchConfigurationError("Unsupported Research initial-condition mode.")

    velocity_mode = config.get("initial_velocity_mode")
    if config["model"] == MODEL_TDGL:
        phi_dot0 = None
        source["phi_dot_initialization"] = "NOT_USED_BY_TDGL"
    elif velocity_mode == "ZERO":
        phi_dot0 = _zero_velocity(phi0)
        source["phi_dot_initialization"] = "USER_SELECTED_EXPLICIT_ZERO"
    elif velocity_mode == "NPZ_ARRAY":
        if phi_dot0 is None:
            raise ResearchConfigurationError(
                "The selected NPZ initial-velocity mode did not materialize an exact phi_dot array."
            )
        source["phi_dot_initialization"] = "PINNED_NPZ_ARRAY"
    else:
        raise ResearchConfigurationError("Second-order Research dynamics require an explicit initial velocity mode.")
    if not np.all(np.isfinite(phi0)):
        raise ResearchConfigurationError("Initial phi must contain only finite values.")
    if phi_dot0 is not None and not np.all(np.isfinite(phi_dot0)):
        raise ResearchConfigurationError("Initial phi_dot must contain only finite values.")
    return phi0, phi_dot0, axes, source


def _resource_review(*, phi0, phi_dot0, config: dict) -> dict:
    elements = int(np.asarray(phi0).size)
    max_elements = int(settings.RESEARCH_FIELD_MAX_ELEMENTS)
    max_steps = int(settings.RESEARCH_FIELD_MAX_STEPS)
    max_output = int(settings.RESEARCH_FIELD_MAX_OUTPUT_BYTES)
    steps = int(config["n_steps"])
    if elements > max_elements:
        raise ResearchConfigurationError(
            f"Research field has {elements} elements; instance limit is {max_elements}."
        )
    if steps > max_steps:
        raise ResearchConfigurationError(
            f"Requested steps = {steps}; instance limit = {max_steps}. No silent truncation is performed."
        )
    trajectories = 1 + int(phi_dot0 is not None)
    estimated = int((steps + 1) * np.asarray(phi0).nbytes * trajectories)
    if estimated > max_output:
        raise ResearchConfigurationError(
            f"Estimated raw trajectory size {estimated} bytes exceeds instance limit {max_output}; the run is refused rather than downsampled."
        )
    return {
        "field_elements": elements,
        "n_steps": steps,
        "estimated_raw_output_bytes": estimated,
        "limits": {
            "max_elements": max_elements,
            "max_steps": max_steps,
            "max_output_bytes": max_output,
        },
    }


def _axis_snapshot(axes) -> list[dict]:
    output = []
    for index, axis in enumerate(axes):
        arr = np.asarray(axis, dtype=float)
        output.append(
            {
                "dimension": index,
                "length": int(arr.size),
                "origin": float(arr[0]),
                "end": float(arr[-1]),
                "spacing": float(arr[1] - arr[0]),
                "dtype": str(arr.dtype),
            }
        )
    return output


def research_field_review_snapshot(analysis: Analysis) -> dict:
    if analysis.analysis_kind != RESEARCH_ANALYSIS_KIND:
        raise ValidationError(_("This Analysis is not a RESEARCH autonomous field Analysis."))
    config = dict(analysis.draft_configuration or {})
    if not config.get("configured"):
        raise ValidationError(_("Complete the RESEARCH field configuration before Review."))
    try:
        phi0, phi_dot0, axes, source = _materialize_initial(analysis, config)
        resource = _resource_review(phi0=phi0, phi_dot0=phi_dot0, config=config)
    except (FieldSourceError, ResearchLabError, ResearchConfigurationError, OSError, ValueError) as exc:
        raise ValidationError(str(exc)) from exc
    boundary = config["boundary_value"]
    return {
        "config": config,
        "source": source,
        "field_shape": list(np.asarray(phi0).shape),
        "phi_dtype": str(np.asarray(phi0).dtype),
        "phi_dot_dtype": None if phi_dot0 is None else str(np.asarray(phi_dot0).dtype),
        "axes": _axis_snapshot(axes),
        "resource": resource,
        "public_function": PUBLIC_APIS[config["model"]],
        "boundary_display": {
            "kind": config["boundary_kind"],
            "real": boundary["real"],
            "imag": boundary["imag"],
        },
        "capabilities": research_capabilities(),
        "scientific_status": RESEARCH_SCIENTIFIC_STATUS,
        "disclaimer": SCIENTIFIC_DISCLAIMER,
        "beta_phi_boundary": BETA_PHI_BOUNDARY,
    }


def _initial_descriptor(snapshot: dict) -> dict:
    return {
        "mode": snapshot["config"]["initial_mode"],
        "velocity_mode": snapshot["config"]["initial_velocity_mode"],
        "source": snapshot["source"],
        "field_shape": snapshot["field_shape"],
        "phi_dtype": snapshot["phi_dtype"],
        "phi_dot_dtype": snapshot["phi_dot_dtype"],
        "axes": snapshot["axes"],
    }


@transaction.atomic
def queue_research_field_run(*, actor, analysis: Analysis) -> AnalysisRun:
    if not can_run_analysis(actor, analysis):
        raise PermissionDenied
    locked = Analysis.objects.select_for_update().select_related("project").get(pk=analysis.pk)
    if locked.status != AnalysisStatus.ACTIVE:
        raise ValidationError(_("Restore the Analysis before running it."))
    snapshot = research_field_review_snapshot(locked)
    config = snapshot["config"]
    context = software_context()
    if context["agencitylab_version"] != "1.2.0":
        raise ValidationError(_("AgencityLab 1.2.0 is required for the Plan 13 RESEARCH contract."))

    phi0, phi_dot0, axes, source = _materialize_initial(locked, config)
    initial_condition = _initial_descriptor(snapshot)
    serialized_input = serialize_research_input(
        phi0=phi0,
        phi_dot0=phi_dot0,
        axes=axes,
        source_snapshot=source,
        initial_condition=initial_condition,
    )
    parameter_snapshot = {
        "lambda": {
            "value": config["lambda"],
            "lab_parameter": "lambda_",
            "origin": config["lambda_origin"],
            "scientific_status": RESEARCH_SCIENTIFIC_STATUS,
        },
        "mu": {
            "value": config["mu"],
            "lab_parameter": "mu",
            "origin": config["mu_origin"],
            "scientific_status": RESEARCH_SCIENTIFIC_STATUS,
        },
        "gamma": {
            "value": config["gamma"],
            "lab_parameter": "gamma",
            "origin": config["gamma_origin"],
            "scientific_status": RESEARCH_SCIENTIFIC_STATUS,
        },
    }
    mapping_snapshot = {
        "spatial_shape": snapshot["field_shape"],
        "spatial_axes": snapshot["axes"],
        "axis_order_significant": True,
        "input_schema": "research-input-v1",
    }
    analysis_options = {
        "scientific_status": RESEARCH_SCIENTIFIC_STATUS,
        "model": config["model"],
        "public_function": snapshot["public_function"],
        "initial_mode": config["initial_mode"],
        "initial_velocity_mode": config["initial_velocity_mode"],
        "units_convention": config["units_convention"],
        "boundary": {
            "kind": config["boundary_kind"],
            "value": dict(config["boundary_value"]),
        },
        "numerical_method": {
            "dt_solver": config["dt_solver"],
            "n_steps": config["n_steps"],
            "label": "NUMERICAL METHOD",
        },
        "postprocessors": {
            "topology_contour_indices": list(config["topology_contour_indices"]),
            "thermo_t_eff": config["thermo_t_eff"],
            "thermo_entropy_a": config["thermo_entropy_a"],
        },
        "scientific_disclaimer": SCIENTIFIC_DISCLAIMER,
        "beta_phi_boundary": BETA_PHI_BOUNDARY,
    }
    fingerprint_payload = {
        "input_sha256": serialized_input.sha256,
        "mapping": mapping_snapshot,
        "parameters": parameter_snapshot,
        "options": analysis_options,
        "agencitylab_version": context["agencitylab_version"],
        "studio_version": context["studio_version"],
    }
    run = AnalysisRun.objects.create(
        analysis=locked,
        run_number=_next_run_number(locked),
        status=RunStatus.QUEUED,
        source_type=SourceType.RESEARCH_FIELD_INPUT,
        source_dataset_version=None,
        source_prepared_artifact=None,
        source_sha256=serialized_input.sha256,
        source_snapshot={
            **source,
            "lineage": [source],
            "input_artifact_sha256": serialized_input.sha256,
        },
        mapping_snapshot=mapping_snapshot,
        system_revision=None,
        system_observable=None,
        system_configuration_fingerprint="",
        parameter_snapshot=parameter_snapshot,
        analysis_options=analysis_options,
        agencitylab_version=context["agencitylab_version"],
        studio_version=context["studio_version"],
        python_version=context["python_version"],
        execution_fingerprint=_fingerprint(fingerprint_payload),
        warnings=[],
        created_by=actor,
        queued_at=timezone.now(),
    )
    artifact_id = uuid.uuid4()
    stored_path = None
    try:
        stored_path = write_research_input(serialized=serialized_input, run=run, artifact_id=artifact_id)
        ResearchFieldInputArtifact.objects.create(
            id=artifact_id,
            run=run,
            storage_path=stored_path,
            format="ZIP_NPY_JSON",
            schema_version=serialized_input.manifest["schema_version"],
            sha256=serialized_input.sha256,
            size_bytes=serialized_input.size_bytes,
            manifest=serialized_input.manifest,
        )
    except Exception:
        if stored_path:
            analysis_storage().delete(stored_path)
        raise
    _record(
        locked,
        actor,
        "ANALYSIS_RUN_QUEUED",
        _("RESEARCH field Run %(number)s queued.") % {"number": run.run_number},
    )
    transaction.on_commit(lambda: _enqueue(run.pk))
    return run


@transaction.atomic
def rerun_research_field(*, actor, run: AnalysisRun) -> AnalysisRun:
    if run.analysis.analysis_kind != RESEARCH_ANALYSIS_KIND:
        raise ValidationError(_("This Run is not a RESEARCH autonomous field Run."))
    if run.status != RunStatus.COMPLETED:
        raise ValidationError(_("Only completed RESEARCH Runs can be rerun exactly."))
    if not can_run_analysis(actor, run.analysis):
        raise PermissionDenied
    locked_analysis = Analysis.objects.select_for_update().get(pk=run.analysis_id)
    source_artifact = run.research_input_artifact
    storage = analysis_storage()
    if not storage.exists(source_artifact.storage_path):
        raise ValidationError(_("The immutable RESEARCH input artifact is unavailable."))
    with storage.open(source_artifact.storage_path, "rb") as handle:
        data = handle.read()
    if hashlib.sha256(data).hexdigest() != source_artifact.sha256:
        raise ValidationError(_("The immutable RESEARCH input artifact failed SHA-256 verification."))

    software = software_context()
    new_run = AnalysisRun.objects.create(
        analysis=locked_analysis,
        run_number=_next_run_number(locked_analysis),
        status=RunStatus.QUEUED,
        source_type=SourceType.RESEARCH_FIELD_INPUT,
        source_sha256=run.source_sha256,
        source_snapshot=run.source_snapshot,
        mapping_snapshot=run.mapping_snapshot,
        parameter_snapshot=run.parameter_snapshot,
        analysis_options=run.analysis_options,
        agencitylab_version=run.agencitylab_version,
        studio_version=software["studio_version"],
        python_version=software["python_version"],
        execution_fingerprint=run.execution_fingerprint,
        warnings=list(run.warnings),
        created_by=actor,
        queued_at=timezone.now(),
    )
    artifact_id = uuid.uuid4()
    path = (
        f"analyses/{new_run.analysis.project_id}/{new_run.analysis_id}/{new_run.pk}/"
        f"{artifact_id}/research-field-input.zip"
    )
    stored_path, size, digest = storage.save_atomic(path, data)
    if size != len(data) or digest != source_artifact.sha256:
        storage.delete(stored_path)
        raise OSError("Copied Research input artifact failed integrity verification.")
    ResearchFieldInputArtifact.objects.create(
        id=artifact_id,
        run=new_run,
        storage_path=stored_path,
        format=source_artifact.format,
        schema_version=source_artifact.schema_version,
        sha256=source_artifact.sha256,
        size_bytes=source_artifact.size_bytes,
        manifest=source_artifact.manifest,
    )
    _record(
        locked_analysis,
        actor,
        "ANALYSIS_RUN_QUEUED",
        _("Exact RESEARCH field rerun %(number)s queued.") % {"number": new_run.run_number},
    )
    transaction.on_commit(lambda: _enqueue(new_run.pk))
    return new_run
