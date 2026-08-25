"""Private result storage and centralized result reader/writer boundary."""

from __future__ import annotations

import hashlib
import uuid

from django.conf import settings

from common.storage import LocalStorage

from .results import load_analysis_result_bytes, serialize_analysis_result


def analysis_storage():
    """Use the shared private web/worker storage root under an Analysis namespace."""
    return LocalStorage(settings.DATASET_STORAGE_ROOT)


def result_artifact_path(run, artifact_id: uuid.UUID) -> str:
    return f"analyses/{run.analysis.project_id}/{run.analysis_id}/{run.pk}/{artifact_id}/canonical-result.zip"


def write_analysis_result(*, result, run, artifact_id: uuid.UUID):
    serialized = serialize_analysis_result(result=result, run=run)
    path = result_artifact_path(run, artifact_id)
    storage = analysis_storage()
    stored_path, size, digest = storage.save_atomic(path, serialized.data)
    if digest != serialized.sha256 or size != serialized.size_bytes:
        storage.delete(stored_path)
        raise OSError("Stored analysis result bytes do not match the serialized result.")
    return stored_path, serialized


def read_analysis_result(run, *, verify_hash: bool = False):
    """Read a completed result through the storage abstraction, never from a public media URL."""
    artifact = run.result_artifact
    storage = analysis_storage()
    if not storage.exists(artifact.storage_path):
        raise OSError("Stored analysis result artifact is missing.")
    with storage.open(artifact.storage_path, "rb") as handle:
        data = handle.read()
    if verify_hash and hashlib.sha256(data).hexdigest() != artifact.sha256:
        raise OSError("Stored analysis result artifact failed SHA-256 verification.")
    return load_analysis_result_bytes(data, expected_run_id=str(run.pk))
