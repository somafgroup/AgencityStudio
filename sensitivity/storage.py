"""Private immutable storage for SensitivityStudy artifacts."""

from __future__ import annotations

import hashlib
import uuid

from analyses.storage import analysis_storage

from .results import StoredSensitivityResult, load_sensitivity_result_bytes, serialize_sensitivity_result


def sensitivity_artifact_path(study, artifact_id: uuid.UUID) -> str:
    run = study.analysis_run
    return (
        f"analyses/{run.analysis.project_id}/{run.analysis_id}/{run.pk}/"
        f"sensitivity/{study.pk}/{artifact_id}/sensitivity-result.zip"
    )


def write_sensitivity_result(*, result: dict, study, artifact_id: uuid.UUID):
    serialized = serialize_sensitivity_result(result=result, study=study)
    path = sensitivity_artifact_path(study, artifact_id)
    storage = analysis_storage()
    stored_path, size, digest = storage.save_atomic(path, serialized.data)
    if digest != serialized.sha256 or size != serialized.size_bytes:
        storage.delete(stored_path)
        raise OSError("Stored sensitivity result bytes do not match the serialized result.")
    return stored_path, serialized


def read_sensitivity_result(study, *, verify_hash: bool = False) -> StoredSensitivityResult:
    artifact = study.result_artifact
    storage = analysis_storage()
    if not storage.exists(artifact.storage_path):
        raise OSError("Stored sensitivity result artifact is missing.")
    with storage.open(artifact.storage_path, "rb") as handle:
        data = handle.read()
    if verify_hash and hashlib.sha256(data).hexdigest() != artifact.sha256:
        raise OSError("Stored sensitivity result artifact failed SHA-256 verification.")
    return load_sensitivity_result_bytes(
        data,
        expected_study_id=str(study.pk),
        expected_canonical_run_id=str(study.analysis_run_id),
    )
