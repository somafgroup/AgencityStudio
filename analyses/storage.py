"""Private result storage and centralized result reader/writer boundary."""

from __future__ import annotations

import hashlib
import uuid
from contextlib import contextmanager

from django.conf import settings

from common.storage import LocalStorage

from .result_reader import AnalysisResultReader
from .results import StoredAnalysisResult, serialize_analysis_result


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


@contextmanager
def open_analysis_result_reader(run, *, verify_hash: bool = False):
    """Open the immutable result through the private storage abstraction.

    ``verify_hash`` is intentionally optional because computing SHA-256 requires a
    full artifact pass. The reader itself validates schema, run identity, series
    inventory, and each requested NumPy payload.
    """
    artifact = run.result_artifact
    storage = analysis_storage()
    if not storage.exists(artifact.storage_path):
        raise OSError("Stored analysis result artifact is missing.")
    with storage.open(artifact.storage_path, "rb") as handle:
        if verify_hash:
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            if digest.hexdigest() != artifact.sha256:
                raise OSError("Stored analysis result artifact failed SHA-256 verification.")
            handle.seek(0)
        with AnalysisResultReader(handle, expected_run_id=str(run.pk)) as reader:
            yield reader


def read_analysis_result(run, *, verify_hash: bool = False) -> StoredAnalysisResult:
    """Read all stored public result series for compatibility and scientific tests."""
    with open_analysis_result_reader(run, verify_hash=verify_hash) as reader:
        arrays = {name: reader.read_series(name) for name in reader.available_series}
        return StoredAnalysisResult(manifest=reader.read_manifest(), arrays=arrays)
