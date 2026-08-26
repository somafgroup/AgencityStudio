"""Private, versioned serialization for AgencityLab diagnostic reports."""

from __future__ import annotations

import hashlib
import io
import json
import math
import zipfile
from dataclasses import dataclass
from typing import Any

import numpy as np

DIAGNOSTIC_SCHEMA_VERSION = "1"
DIAGNOSTIC_FORMAT = "ZIP_JSON"
NONFINITE_KEY = "__agencitystudio_nonfinite__"


class DiagnosticArtifactError(ValueError):
    """Stored diagnostic result is missing, corrupt, or incompatible."""


@dataclass(frozen=True)
class SerializedDiagnosticResult:
    data: bytes
    sha256: str
    size_bytes: int
    manifest: dict


@dataclass(frozen=True)
class StoredDiagnosticResult:
    manifest: dict
    report: dict


def _encode(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [_encode(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return _encode(value.item())
    if isinstance(value, float):
        if math.isnan(value):
            return {NONFINITE_KEY: "nan"}
        if math.isinf(value):
            return {NONFINITE_KEY: "positive_infinity" if value > 0 else "negative_infinity"}
        return value
    if isinstance(value, complex):
        return {
            "__agencitystudio_complex__": True,
            "real": _encode(float(value.real)),
            "imag": _encode(float(value.imag)),
        }
    if isinstance(value, dict):
        return {str(key): _encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(item) for item in value]
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, dict):
        marker = value.get(NONFINITE_KEY)
        if marker == "nan":
            return float("nan")
        if marker == "positive_infinity":
            return float("inf")
        if marker == "negative_infinity":
            return float("-inf")
        if value.get("__agencitystudio_complex__") is True:
            return complex(_decode(value.get("real")), _decode(value.get("imag")))
        return {str(key): _decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode(item) for item in value]
    return value


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        _encode(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def serialize_diagnostic_result(*, report: dict, diagnostic_run) -> SerializedDiagnosticResult:
    """Serialize one Lab report without inventing or collapsing diagnostic values."""
    manifest = {
        "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
        "format": DIAGNOSTIC_FORMAT,
        "diagnostic_run_id": str(diagnostic_run.pk),
        "canonical_run_id": str(diagnostic_run.analysis_run_id),
        "canonical_result_sha256": diagnostic_run.canonical_result_sha256,
        "diagnostic_execution_fingerprint": diagnostic_run.execution_fingerprint,
        "agencitylab_version": diagnostic_run.agencitylab_version,
        "studio_version": diagnostic_run.studio_version,
        "diagnostic_api_identifiers": list(diagnostic_run.diagnostic_api_identifiers),
        "diagnostic_configuration": diagnostic_run.diagnostic_configuration,
        "lab_analysis_schema_version": report.get("analysis_schema_version"),
        "available_sections": sorted(str(key) for key in report),
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, payload in (("manifest.json", manifest), ("report.json", report)):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, _json_bytes(payload))
    data = buffer.getvalue()
    return SerializedDiagnosticResult(
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        manifest=manifest,
    )


def load_diagnostic_result_bytes(
    data: bytes,
    *,
    expected_diagnostic_run_id: str | None = None,
    expected_canonical_run_id: str | None = None,
) -> StoredDiagnosticResult:
    """Read and validate one immutable diagnostic result archive."""
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            manifest = _decode(json.loads(archive.read("manifest.json")))
            report = _decode(json.loads(archive.read("report.json")))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        raise DiagnosticArtifactError(
            "Stored diagnostic result is unavailable or corrupt."
        ) from exc

    if manifest.get("schema_version") != DIAGNOSTIC_SCHEMA_VERSION:
        raise DiagnosticArtifactError("Unsupported diagnostic result schema version.")
    if manifest.get("format") != DIAGNOSTIC_FORMAT:
        raise DiagnosticArtifactError("Unsupported diagnostic result format.")
    if expected_diagnostic_run_id and manifest.get("diagnostic_run_id") != str(
        expected_diagnostic_run_id
    ):
        raise DiagnosticArtifactError("Stored diagnostic result belongs to another DiagnosticRun.")
    if expected_canonical_run_id and manifest.get("canonical_run_id") != str(
        expected_canonical_run_id
    ):
        raise DiagnosticArtifactError("Stored diagnostic result references another canonical Run.")
    if not isinstance(report, dict):
        raise DiagnosticArtifactError("Stored diagnostic report is invalid.")
    return StoredDiagnosticResult(manifest=manifest, report=report)
