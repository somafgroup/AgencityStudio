"""Private storage helpers for immutable observable-field result artifacts."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager

from .field_result_reader import ObservableFieldResultReader
from .field_results import serialize_observable_field_result
from .storage import analysis_storage


def field_result_path(run, artifact_id) -> str:
    return (
        f"analyses/{run.analysis.project_id}/{run.analysis_id}/{run.pk}/{artifact_id}/"
        "observable-field-result.zip"
    )


def write_observable_field_result(*, result, run, artifact_id):
    serialized = serialize_observable_field_result(result=result, run=run)
    path = field_result_path(run, artifact_id)
    storage = analysis_storage()
    stored_path, size, digest = storage.save_atomic(path, serialized.data)
    if size != serialized.size_bytes or digest != serialized.sha256:
        storage.delete(stored_path)
        raise OSError("Stored observable field result bytes do not match serialization.")
    return stored_path, serialized


@contextmanager
def open_observable_field_result_reader(run, *, verify_hash: bool = False):
    artifact = run.result_artifact
    storage = analysis_storage()
    if not storage.exists(artifact.storage_path):
        raise OSError("Stored observable field result artifact is missing.")
    with storage.open(artifact.storage_path, "rb") as handle:
        if verify_hash:
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            if digest.hexdigest() != artifact.sha256:
                raise OSError("Stored observable field result failed SHA-256 verification.")
            handle.seek(0)
        with ObservableFieldResultReader(handle, expected_run_id=str(run.pk)) as reader:
            yield reader
