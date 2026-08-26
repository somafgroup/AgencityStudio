"""Private versioned serialization for multiscale and window sensitivity outputs."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from typing import Any

import numpy as np

SENSITIVITY_SCHEMA_VERSION = "1"
SENSITIVITY_FORMAT = "ZIP_NPY_JSON"


class SensitivityArtifactError(ValueError):
    """Stored sensitivity result is missing, corrupt, or incompatible."""


@dataclass(frozen=True)
class SerializedSensitivityResult:
    data: bytes
    sha256: str
    size_bytes: int
    manifest: dict


@dataclass(frozen=True)
class StoredSensitivityResult:
    manifest: dict
    arrays: dict[str, np.ndarray]
    scalars: dict[str, Any]


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, complex):
        return {"complex": True, "real": float(value.real), "imag": float(value.imag)}
    if isinstance(value, float) and not np.isfinite(value):
        return {"nonfinite": "nan" if np.isnan(value) else ("inf" if value > 0 else "-inf")}
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _json_restore(value: Any) -> Any:
    if isinstance(value, dict):
        if value.get("complex") is True:
            return complex(value["real"], value["imag"])
        if value.get("nonfinite") == "nan":
            return float("nan")
        if value.get("nonfinite") == "inf":
            return float("inf")
        if value.get("nonfinite") == "-inf":
            return float("-inf")
        return {str(key): _json_restore(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_restore(item) for item in value]
    return value


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        _json_safe(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def serialize_sensitivity_result(*, result: dict, study) -> SerializedSensitivityResult:
    """Serialize exact public Lab outputs without changing dtype or precision."""
    arrays: dict[str, np.ndarray] = {}
    scalars: dict[str, Any] = {}
    series_manifest: list[dict[str, Any]] = []
    for name, value in result.items():
        if isinstance(value, np.ndarray):
            array = np.asarray(value)
            arrays[str(name)] = array
            series_manifest.append(
                {"name": str(name), "shape": list(array.shape), "dtype": str(array.dtype)}
            )
        else:
            scalars[str(name)] = value

    manifest = {
        "schema_version": SENSITIVITY_SCHEMA_VERSION,
        "format": SENSITIVITY_FORMAT,
        "study_id": str(study.pk),
        "canonical_run_id": str(study.analysis_run_id),
        "canonical_result_sha256": study.canonical_result_sha256,
        "source_sha256": study.source_sha256,
        "study_type": study.study_type,
        "scientific_status": study.scientific_status,
        "study_execution_fingerprint": study.execution_fingerprint,
        "public_api_identifier": study.public_api_identifier,
        "agencitylab_version": study.agencitylab_version,
        "studio_version": study.studio_version,
        "grid_type": study.grid_type,
        "grid_unit": study.grid_unit,
        "requested_grid": study.requested_grid,
        "study_configuration": study.study_configuration,
        "series": sorted(series_manifest, key=lambda item: item["name"]),
        "scalar_keys": sorted(scalars),
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, payload in (("manifest.json", manifest), ("scalars.json", scalars)):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, _json_bytes(payload))
        for name in sorted(arrays):
            array_buffer = io.BytesIO()
            np.save(array_buffer, arrays[name], allow_pickle=False)
            info = zipfile.ZipInfo(f"arrays/{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, array_buffer.getvalue())

    data = buffer.getvalue()
    return SerializedSensitivityResult(
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        manifest=manifest,
    )


def load_sensitivity_result_bytes(
    data: bytes,
    *,
    expected_study_id: str | None = None,
    expected_canonical_run_id: str | None = None,
) -> StoredSensitivityResult:
    """Read and validate one immutable sensitivity result archive."""
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            manifest = json.loads(archive.read("manifest.json"))
            scalars = _json_restore(json.loads(archive.read("scalars.json")))
            arrays = {
                item["name"]: np.load(
                    io.BytesIO(archive.read(f"arrays/{item['name']}.npy")),
                    allow_pickle=False,
                )
                for item in manifest.get("series", [])
            }
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        raise SensitivityArtifactError(
            "Stored sensitivity result is unavailable or corrupt."
        ) from exc

    if manifest.get("schema_version") != SENSITIVITY_SCHEMA_VERSION:
        raise SensitivityArtifactError("Unsupported sensitivity result schema version.")
    if manifest.get("format") != SENSITIVITY_FORMAT:
        raise SensitivityArtifactError("Unsupported sensitivity result format.")
    if expected_study_id and manifest.get("study_id") != str(expected_study_id):
        raise SensitivityArtifactError("Stored result belongs to another sensitivity study.")
    if expected_canonical_run_id and manifest.get("canonical_run_id") != str(expected_canonical_run_id):
        raise SensitivityArtifactError("Stored result references another canonical Run.")
    return StoredSensitivityResult(manifest=manifest, arrays=arrays, scalars=scalars)
