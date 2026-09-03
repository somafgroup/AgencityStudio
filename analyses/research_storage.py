"""Private storage helpers for immutable RESEARCH field input/result artifacts."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager

from .research_contract import RESEARCH_INPUT_SCHEMA_VERSION, RESEARCH_RESULT_SCHEMA_VERSION
from .research_result_reader import ResearchFieldResultReader
from .research_results import serialize_research_result
from .storage import analysis_storage


def research_input_path(run, artifact_id) -> str:
    return (
        f"analyses/{run.analysis.project_id}/{run.analysis_id}/{run.pk}/{artifact_id}/"
        "research-field-input.zip"
    )


def research_result_path(run, artifact_id) -> str:
    return (
        f"analyses/{run.analysis.project_id}/{run.analysis_id}/{run.pk}/{artifact_id}/"
        "research-field-result.zip"
    )


def write_research_input(*, serialized, run, artifact_id):
    path = research_input_path(run, artifact_id)
    storage = analysis_storage()
    stored_path, size, digest = storage.save_atomic(path, serialized.data)
    if size != serialized.size_bytes or digest != serialized.sha256:
        storage.delete(stored_path)
        raise OSError("Stored Research field input bytes do not match serialization.")
    return stored_path


def write_research_result(*, execution, run, artifact_id):
    serialized = serialize_research_result(execution=execution, run=run)
    path = research_result_path(run, artifact_id)
    storage = analysis_storage()
    stored_path, size, digest = storage.save_atomic(path, serialized.data)
    if size != serialized.size_bytes or digest != serialized.sha256:
        storage.delete(stored_path)
        raise OSError("Stored Research field result bytes do not match serialization.")
    return stored_path, serialized


@contextmanager
def open_research_input_reader(run, *, verify_hash: bool = False):
    artifact = run.research_input_artifact
    storage = analysis_storage()
    if not storage.exists(artifact.storage_path):
        raise OSError("Stored Research field input artifact is missing.")
    with storage.open(artifact.storage_path, "rb") as handle:
        if verify_hash:
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            if digest.hexdigest() != artifact.sha256:
                raise OSError("Stored Research field input failed SHA-256 verification.")
            handle.seek(0)
        with ResearchFieldResultReader(
            handle,
            expected_schema=RESEARCH_INPUT_SCHEMA_VERSION,
        ) as reader:
            yield reader


@contextmanager
def open_research_result_reader(run, *, verify_hash: bool = False):
    artifact = run.result_artifact
    storage = analysis_storage()
    if not storage.exists(artifact.storage_path):
        raise OSError("Stored Research field result artifact is missing.")
    with storage.open(artifact.storage_path, "rb") as handle:
        if verify_hash:
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            if digest.hexdigest() != artifact.sha256:
                raise OSError("Stored Research field result failed SHA-256 verification.")
            handle.seek(0)
        with ResearchFieldResultReader(
            handle,
            expected_schema=RESEARCH_RESULT_SCHEMA_VERSION,
            expected_run_id=str(run.pk),
        ) as reader:
            yield reader
