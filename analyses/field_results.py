"""Lossless ZIP/NPY/JSON serialization for ObservableAgencityFieldResult."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass

import numpy as np

from .field_contract import FIELD_RESULT_SCHEMA_VERSION, FIELD_SCIENTIFIC_STATUS

FIELD_RESULT_FORMAT = "ZIP_NPY_JSON"
FIELD_SERIES = (
    "t",
    "u",
    "u_star",
    "X_star",
    "A_star",
    "M",
    "O",
    "D",
    "S",
    "J",
    "U",
    "beta",
    "b",
    "A_ref",
    "tau",
    "w",
    "P_c",
)
FIELD_ALIASES = {"beta_obs": "beta", "b_obs": "b"}


class FieldResultArtifactError(ValueError):
    """Stored observable field result is missing, corrupt, or incompatible."""


@dataclass(frozen=True)
class SerializedFieldResult:
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
    np.lib.format.write_array(payload, array, allow_pickle=False)
    return payload.getvalue()


def serialize_observable_field_result(*, result, run) -> SerializedFieldResult:
    """Serialize only public result attributes, preserving N-D shape/dtype/complex values."""

    arrays: dict[str, np.ndarray] = {}
    inventory: list[dict] = []
    for name in FIELD_SERIES:
        value = getattr(result, name, None)
        if value is None:
            continue
        array = np.asarray(value)
        arrays[name] = array
        inventory.append(
            {
                "name": name,
                "shape": list(array.shape),
                "dtype": str(array.dtype),
                "member": f"arrays/{name}.npy",
                "complex": bool(np.iscomplexobj(array)),
            }
        )
    for index, axis in enumerate(tuple(result.spatial_axes)):
        name = f"spatial_axis_{index}"
        array = np.asarray(axis)
        arrays[name] = array
        inventory.append(
            {
                "name": name,
                "shape": list(array.shape),
                "dtype": str(array.dtype),
                "member": f"arrays/{name}.npy",
                "complex": False,
            }
        )

    lab_metadata = dict(getattr(result, "metadata", {}) or {})
    manifest = {
        "schema_version": FIELD_RESULT_SCHEMA_VERSION,
        "format": FIELD_RESULT_FORMAT,
        "run_id": str(run.pk),
        "analysis_id": str(run.analysis_id),
        "scientific_status": FIELD_SCIENTIFIC_STATUS,
        "lab_status": str(result.status),
        "model": str(result.model),
        "backend": str(result.backend),
        "public_function": run.analysis_options.get("public_function"),
        "source_sha256": run.source_sha256,
        "system_revision_id": str(run.system_revision_id),
        "system_configuration_fingerprint": run.system_configuration_fingerprint,
        "execution_fingerprint": run.execution_fingerprint,
        "agencitylab_version": run.agencitylab_version,
        "studio_version": run.studio_version,
        "field_shape": list(np.asarray(result.u).shape),
        "time_axis": int(result.time_axis),
        "spatial_shape": list(result.spatial_shape),
        "spatial_axes": list(run.mapping_snapshot.get("spatial_axes", [])),
        "spatial_axes_mode": run.mapping_snapshot.get("spatial_axes_mode"),
        "parameter_modes": {
            name: run.parameter_snapshot[name].get("mode")
            for name in ("A_ref", "tau", "w", "P_c")
        },
        "crm_scope": lab_metadata.get(
            "crm_scope", "temporal_only_independent_at_each_spatial_location"
        ),
        "series": inventory,
        "aliases": dict(FIELD_ALIASES),
        "lab_metadata": _json_safe(lab_metadata),
        "scientific_boundary": (
            "Observable field derived from u(x,t) by experimental spatial orchestration of the canonical temporal pipeline; not autonomous phi dynamics."
        ),
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        info = zipfile.ZipInfo("manifest.json", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(
            info,
            json.dumps(
                manifest,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8"),
        )
        for item in inventory:
            name = item["name"]
            info = zipfile.ZipInfo(item["member"], date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, _npy_bytes(arrays[name]))
    data = buffer.getvalue()
    return SerializedFieldResult(
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        manifest=manifest,
    )
