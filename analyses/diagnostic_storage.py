"""Private immutable storage for scientific DiagnosticRun artifacts."""

from __future__ import annotations

import hashlib
import uuid

from .diagnostic_results import (
    StoredDiagnosticResult,
    load_diagnostic_result_bytes,
    serialize_diagnostic_result,
)
from .storage import analysis_storage


def diagnostic_artifact_path(diagnostic_run, artifact_id: uuid.UUID) -> str:
    canonical = diagnostic_run.analysis_run
    return (
        f"analyses/{canonical.analysis.project_id}/{canonical.analysis_id}/"
        f"{canonical.pk}/diagnostics/{diagnostic_run.pk}/{artifact_id}/diagnostic-result.zip"
    )


def write_diagnostic_result(*, report: dict, diagnostic_run, artifact_id: uuid.UUID):
    serialized = serialize_diagnostic_result(report=report, diagnostic_run=diagnostic_run)
    path = diagnostic_artifact_path(diagnostic_run, artifact_id)
    storage = analysis_storage()
    stored_path, size, digest = storage.save_atomic(path, serialized.data)
    if digest != serialized.sha256 or size != serialized.size_bytes:
        storage.delete(stored_path)
        raise OSError("Stored diagnostic result bytes do not match the serialized result.")
    return stored_path, serialized


def read_diagnostic_result(diagnostic_run, *, verify_hash: bool = False) -> StoredDiagnosticResult:
    artifact = diagnostic_run.result_artifact
    storage = analysis_storage()
    if not storage.exists(artifact.storage_path):
        raise OSError("Stored diagnostic result artifact is missing.")
    with storage.open(artifact.storage_path, "rb") as handle:
        data = handle.read()
    if verify_hash and hashlib.sha256(data).hexdigest() != artifact.sha256:
        raise OSError("Stored diagnostic result artifact failed SHA-256 verification.")
    return load_diagnostic_result_bytes(
        data,
        expected_diagnostic_run_id=str(diagnostic_run.pk),
        expected_canonical_run_id=str(diagnostic_run.analysis_run_id),
    )
