"""Validated read-only access to stored autonomous RESEARCH field artifacts."""

from __future__ import annotations

import json
import zipfile

import numpy as np

from .research_contract import RESEARCH_INPUT_SCHEMA_VERSION, RESEARCH_RESULT_SCHEMA_VERSION
from .research_results import ResearchArtifactError


class ResearchFieldResultReader:
    """Read an immutable research artifact without recalculating scientific values."""

    def __init__(self, handle, *, expected_schema: str, expected_run_id: str | None = None):
        self.handle = handle
        self.expected_schema = expected_schema
        self.expected_run_id = str(expected_run_id) if expected_run_id else None
        self.archive: zipfile.ZipFile | None = None
        self._manifest: dict | None = None

    def __enter__(self):
        try:
            self.archive = zipfile.ZipFile(self.handle, "r")
            manifest = json.loads(self.archive.read("manifest.json"))
        except (OSError, ValueError, KeyError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
            raise ResearchArtifactError("Stored Research field artifact is unavailable or corrupt.") from exc
        if manifest.get("schema_version") != self.expected_schema:
            raise ResearchArtifactError("Unsupported Research field artifact schema version.")
        if self.expected_run_id and manifest.get("run_id") != self.expected_run_id:
            raise ResearchArtifactError("Stored Research field result belongs to another Run.")
        self._manifest = manifest
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.archive is not None:
            self.archive.close()
        self.archive = None
        return False

    def read_manifest(self) -> dict:
        if self._manifest is None:
            raise ResearchArtifactError("Research field reader is not open.")
        return dict(self._manifest)

    @property
    def available_series(self) -> tuple[str, ...]:
        return tuple(item["name"] for item in self.read_manifest().get("series", []))

    def _descriptor(self, name: str) -> dict:
        for item in self.read_manifest().get("series", []):
            if item.get("name") == name:
                return item
        raise ResearchArtifactError(f"Stored Research field series {name!r} is unavailable.")

    def read_series(self, name: str) -> np.ndarray:
        if self.archive is None:
            raise ResearchArtifactError("Research field reader is not open.")
        descriptor = self._descriptor(name)
        try:
            with self.archive.open(descriptor["member"], "r") as handle:
                array = np.load(handle, allow_pickle=False)
        except (OSError, ValueError, KeyError) as exc:
            raise ResearchArtifactError(
                f"Stored Research field series {name!r} is unavailable or corrupt."
            ) from exc
        if list(array.shape) != list(descriptor["shape"]) or str(array.dtype) != descriptor["dtype"]:
            raise ResearchArtifactError(
                f"Stored Research field series {name!r} does not match its manifest."
            )
        return array

    def time_slice(self, name: str, time_index: int) -> np.ndarray:
        array = self.read_series(name)
        index = int(time_index)
        if array.ndim < 1 or index < 0 or index >= array.shape[0]:
            raise ResearchArtifactError("Requested time index is outside the stored trajectory.")
        return np.asarray(array[index])

    def spatial_point_series(self, name: str, spatial_index: tuple[int, ...]) -> np.ndarray:
        array = self.read_series(name)
        spatial_shape = tuple(int(value) for value in self.read_manifest()["spatial_shape"])
        index = tuple(int(value) for value in spatial_index)
        if len(index) != len(spatial_shape):
            raise ResearchArtifactError("Spatial index rank does not match the stored Research field.")
        if any(value < 0 or value >= length for value, length in zip(index, spatial_shape, strict=True)):
            raise ResearchArtifactError("Requested spatial index is outside the stored Research field.")
        return np.asarray(array[(slice(None), *index)])

    def exact_point(self, name: str, time_index: int, spatial_index: tuple[int, ...]):
        trace = self.spatial_point_series(name, spatial_index)
        index = int(time_index)
        if index < 0 or index >= trace.shape[0]:
            raise ResearchArtifactError("Requested time index is outside the stored trajectory.")
        return trace[index]

    def spatial_slice(
        self,
        name: str,
        *,
        time_index: int,
        display_dimensions: tuple[int, ...],
        fixed_indices: dict[int, int] | None = None,
    ) -> np.ndarray:
        """Return an exact 1D/2D spatial slice without averaging or interpolation."""

        spatial = self.time_slice(name, time_index)
        spatial_shape = tuple(int(value) for value in self.read_manifest()["spatial_shape"])
        display = tuple(int(value) for value in display_dimensions)
        if not 1 <= len(display) <= 2 or len(set(display)) != len(display):
            raise ResearchArtifactError("Select one or two distinct spatial display dimensions.")
        if any(value < 0 or value >= len(spatial_shape) for value in display):
            raise ResearchArtifactError("A spatial display dimension is outside the stored field.")
        fixed = {int(key): int(value) for key, value in (fixed_indices or {}).items()}
        selector: list[object] = []
        for dimension, length in enumerate(spatial_shape):
            if dimension in display:
                selector.append(slice(None))
            else:
                value = fixed.get(dimension, 0)
                if value < 0 or value >= length:
                    raise ResearchArtifactError("A fixed spatial index is outside the stored field.")
                selector.append(value)
        sliced = np.asarray(spatial[tuple(selector)])
        remaining = [dimension for dimension in range(len(spatial_shape)) if dimension in display]
        if remaining != list(display) and sliced.ndim == 2:
            sliced = np.transpose(sliced)
        return sliced


def result_reader(handle, *, run_id: str):
    return ResearchFieldResultReader(
        handle,
        expected_schema=RESEARCH_RESULT_SCHEMA_VERSION,
        expected_run_id=run_id,
    )


def input_reader(handle):
    return ResearchFieldResultReader(handle, expected_schema=RESEARCH_INPUT_SCHEMA_VERSION)
