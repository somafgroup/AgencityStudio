"""Private, versioned, lossless serialization for public AgencityResult values."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass

import numpy as np

RESULT_SCHEMA_VERSION = "1"
RESULT_FORMAT = "ZIP_NPY_JSON"
CANONICAL_SERIES = (
    "xi",
    "u",
    "u_star",
    "X_star",
    "A_star",
    "t_star",
    "M",
    "O",
    "D",
    "S",
    "J",
    "theta",
    "U",
    "beta",
    "b",
)


class ResultArtifactError(ValueError):
    """Stored canonical result is missing, corrupt, or incompatible."""


@dataclass(frozen=True)
class SerializedResult:
    data: bytes
    sha256: str
    size_bytes: int
    manifest: dict


@dataclass(frozen=True)
class StoredAnalysisResult:
    manifest: dict
    arrays: dict[str, np.ndarray]


def _json_safe(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def serialize_analysis_result(*, result, run) -> SerializedResult:
    """Serialize public result fields without downcasting or private Lab attributes."""
    arrays: dict[str, np.ndarray] = {}
    inventory: list[dict] = []
    for name in CANONICAL_SERIES:
        value = getattr(result, name, None)
        if value is None:
            continue
        array = np.asarray(value)
        arrays[name] = array
        inventory.append({"name": name, "shape": list(array.shape), "dtype": str(array.dtype)})

    metadata = result.metadata.to_dict() if hasattr(result.metadata, "to_dict") else {}
    manifest = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "format": RESULT_FORMAT,
        "run_id": str(run.pk),
        "analysis_id": str(run.analysis_id),
        "source_sha256": run.source_sha256,
        "system_revision_id": str(run.system_revision_id),
        "system_configuration_fingerprint": run.system_configuration_fingerprint,
        "execution_fingerprint": run.execution_fingerprint,
        "agencitylab_version": run.agencitylab_version,
        "studio_version": run.studio_version,
        "series": inventory,
        "units": {
            "observable": result.unit,
            "coordinate": result.coordinate_unit,
            "power": result.power_unit,
            "agencity_flux": result.b_unit,
        },
        "result_context": {
            "A_ref": float(result.A_ref),
            "tau": float(result.tau),
            "P_c": float(result.P_c) if np.asarray(result.P_c).ndim == 0 else _json_safe(np.asarray(result.P_c)),
            "effective_w": result.memory_window,
            "observable_kind": result.observable_kind,
            "domain": result.domain,
            "system_type": result.system_type,
            "mechanism": result.mechanism,
        },
        "lab_metadata": _json_safe(metadata),
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        info = zipfile.ZipInfo("manifest.json", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        for name in CANONICAL_SERIES:
            if name not in arrays:
                continue
            payload = io.BytesIO()
            np.lib.format.write_array(payload, arrays[name], allow_pickle=False)
            info = zipfile.ZipInfo(f"arrays/{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payload.getvalue())
    data = buffer.getvalue()
    return SerializedResult(
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        manifest=manifest,
    )


def load_analysis_result_bytes(data: bytes, *, expected_run_id: str | None = None) -> StoredAnalysisResult:
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            manifest = json.loads(archive.read("manifest.json"))
            if manifest.get("schema_version") != RESULT_SCHEMA_VERSION:
                raise ResultArtifactError("Unsupported analysis result schema version.")
            if expected_run_id and manifest.get("run_id") != str(expected_run_id):
                raise ResultArtifactError("Stored result belongs to a different AnalysisRun.")
            arrays: dict[str, np.ndarray] = {}
            for item in manifest.get("series", []):
                name = item["name"]
                with archive.open(f"arrays/{name}.npy", "r") as handle:
                    arrays[name] = np.load(handle, allow_pickle=False)
                if list(arrays[name].shape) != list(item.get("shape", [])) or str(arrays[name].dtype) != item.get("dtype"):
                    raise ResultArtifactError(f"Stored series {name} does not match its manifest.")
    except (KeyError, OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        if isinstance(exc, ResultArtifactError):
            raise
        raise ResultArtifactError("Stored analysis result is unavailable or corrupt.") from exc
    return StoredAnalysisResult(manifest=manifest, arrays=arrays)
