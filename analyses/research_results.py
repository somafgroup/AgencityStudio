"""Lossless private artifacts for autonomous RESEARCH field inputs and outputs."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass

import numpy as np

from .research_contract import (
    BETA_PHI_BOUNDARY,
    RESEARCH_INPUT_SCHEMA_VERSION,
    RESEARCH_RESULT_SCHEMA_VERSION,
    RESEARCH_SCIENTIFIC_STATUS,
    SCIENTIFIC_DISCLAIMER,
)

RESEARCH_ARTIFACT_FORMAT = "ZIP_NPY_JSON"


class ResearchArtifactError(ValueError):
    """Stored research field input/result is missing, corrupt, or incompatible."""


@dataclass(frozen=True)
class SerializedResearchArtifact:
    data: bytes
    sha256: str
    size_bytes: int
    manifest: dict


def _json_safe(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _npy_bytes(array: np.ndarray) -> bytes:
    payload = io.BytesIO()
    np.lib.format.write_array(payload, np.asarray(array), allow_pickle=False)
    return payload.getvalue()


def _serialize(*, manifest: dict, arrays: dict[str, np.ndarray]) -> SerializedResearchArtifact:
    inventory = []
    for name, value in arrays.items():
        array = np.asarray(value)
        if array.dtype.hasobject:
            raise ResearchArtifactError("Research artifacts cannot contain object/pickle arrays.")
        inventory.append(
            {
                "name": name,
                "shape": list(array.shape),
                "dtype": str(array.dtype),
                "member": f"arrays/{name}.npy",
                "complex": bool(np.iscomplexobj(array)),
            }
        )
    payload_manifest = {**manifest, "series": inventory}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        info = zipfile.ZipInfo("manifest.json", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(
            info,
            json.dumps(
                _json_safe(payload_manifest),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8"),
        )
        for item in inventory:
            info = zipfile.ZipInfo(item["member"], date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, _npy_bytes(arrays[item["name"]]))
    data = buffer.getvalue()
    return SerializedResearchArtifact(
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        manifest=payload_manifest,
    )


def serialize_research_input(
    *,
    phi0,
    phi_dot0,
    axes,
    source_snapshot: dict,
    initial_condition: dict,
) -> SerializedResearchArtifact:
    """Freeze exact initial state and geometry before a Research Run is queued."""

    arrays = {"phi0": np.asarray(phi0)}
    if phi_dot0 is not None:
        arrays["phi_dot0"] = np.asarray(phi_dot0)
    for index, axis in enumerate(tuple(axes)):
        arrays[f"spatial_axis_{index}"] = np.asarray(axis)
    manifest = {
        "schema_version": RESEARCH_INPUT_SCHEMA_VERSION,
        "format": RESEARCH_ARTIFACT_FORMAT,
        "scientific_status": RESEARCH_SCIENTIFIC_STATUS,
        "initial_condition": dict(initial_condition),
        "source_snapshot": dict(source_snapshot),
        "spatial_shape": list(np.asarray(phi0).shape),
        "axis_order_significant": True,
        "scientific_boundary": BETA_PHI_BOUNDARY,
    }
    return _serialize(manifest=manifest, arrays=arrays)


def serialize_research_result(*, execution, run) -> SerializedResearchArtifact:
    """Serialize the public DynamicalAgencityFieldSolution without dtype or shape loss."""

    result = execution.result
    arrays: dict[str, np.ndarray] = {
        "times": np.asarray(result.times),
        "phi": np.asarray(result.phi),
    }
    if result.phi_dot is not None:
        arrays["phi_dot"] = np.asarray(result.phi_dot)
    for index, axis in enumerate(tuple(result.spatial_axes or ())):
        arrays[f"spatial_axis_{index}"] = np.asarray(axis)
    for name, value in execution.derived.items():
        arrays[name] = np.asarray(value)

    manifest = {
        "schema_version": RESEARCH_RESULT_SCHEMA_VERSION,
        "format": RESEARCH_ARTIFACT_FORMAT,
        "run_id": str(run.pk),
        "analysis_id": str(run.analysis_id),
        "scientific_status": RESEARCH_SCIENTIFIC_STATUS,
        "disclaimer": SCIENTIFIC_DISCLAIMER,
        "scientific_boundary": BETA_PHI_BOUNDARY,
        "model": run.analysis_options.get("model"),
        "public_function": run.analysis_options.get("public_function"),
        "dynamics_name": str(result.dynamics_name),
        "boundary_name": str(result.boundary_name),
        "units_convention": str(result.units_convention),
        "spatial_shape": list(result.spatial_shape),
        "n_time": int(np.asarray(result.times).size),
        "input_sha256": run.source_sha256,
        "execution_fingerprint": run.execution_fingerprint,
        "agencitylab_version": run.agencitylab_version,
        "studio_version": run.studio_version,
        "parameters": _json_safe(dict(result.parameters or {})),
        "parameter_provenance": _json_safe(
            {
                key: item.to_dict() if hasattr(item, "to_dict") else item
                for key, item in dict(result.parameter_provenance or {}).items()
            }
        ),
        "solver_metadata": _json_safe(dict(result.solver_metadata or {})),
        "lab_metadata": _json_safe(dict(result.metadata or {})),
        "derived_public_outputs": sorted(execution.derived),
    }
    return _serialize(manifest=manifest, arrays=arrays)
