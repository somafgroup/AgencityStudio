"""Validated reader and exact N-dimensional slicing for stored observable fields."""

from __future__ import annotations

import json
import zipfile

import numpy as np

from .field_contract import FIELD_RESULT_SCHEMA_VERSION
from .field_results import FieldResultArtifactError


class ObservableFieldResultReader:
    """Read one immutable field artifact without exposing its storage path."""

    def __init__(self, handle, *, expected_run_id: str | None = None):
        self.handle = handle
        self.expected_run_id = str(expected_run_id) if expected_run_id else None
        self.archive: zipfile.ZipFile | None = None
        self._manifest: dict | None = None

    def __enter__(self):
        try:
            self.archive = zipfile.ZipFile(self.handle, "r")
            manifest = json.loads(self.archive.read("manifest.json"))
        except (OSError, ValueError, KeyError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
            raise FieldResultArtifactError("Stored observable field result is unavailable or corrupt.") from exc
        if manifest.get("schema_version") != FIELD_RESULT_SCHEMA_VERSION:
            raise FieldResultArtifactError("Unsupported observable field result schema version.")
        if self.expected_run_id and manifest.get("run_id") != self.expected_run_id:
            raise FieldResultArtifactError("Stored observable field result belongs to another Run.")
        self._manifest = manifest
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.archive is not None:
            self.archive.close()
        self.archive = None
        return False

    def read_manifest(self) -> dict:
        if self._manifest is None:
            raise FieldResultArtifactError("Field result reader is not open.")
        return dict(self._manifest)

    @property
    def available_series(self) -> tuple[str, ...]:
        manifest = self.read_manifest()
        names = [item["name"] for item in manifest.get("series", [])]
        names.extend(manifest.get("aliases", {}).keys())
        return tuple(names)

    def _descriptor(self, name: str) -> tuple[str, dict]:
        manifest = self.read_manifest()
        canonical = manifest.get("aliases", {}).get(name, name)
        for item in manifest.get("series", []):
            if item.get("name") == canonical:
                return canonical, item
        raise FieldResultArtifactError(f"Stored field series {name!r} is unavailable.")

    def read_series(self, name: str) -> np.ndarray:
        if self.archive is None:
            raise FieldResultArtifactError("Field result reader is not open.")
        canonical, descriptor = self._descriptor(name)
        try:
            with self.archive.open(descriptor["member"], "r") as handle:
                array = np.load(handle, allow_pickle=False)
        except (OSError, ValueError, KeyError) as exc:
            raise FieldResultArtifactError(
                f"Stored field series {canonical!r} is unavailable or corrupt."
            ) from exc
        if list(array.shape) != list(descriptor["shape"]) or str(array.dtype) != descriptor["dtype"]:
            raise FieldResultArtifactError(
                f"Stored field series {canonical!r} does not match its manifest."
            )
        return array

    def time_slice(self, name: str, time_index: int) -> np.ndarray:
        array = self.read_series(name)
        manifest = self.read_manifest()
        axis = int(manifest["time_axis"])
        index = int(time_index)
        if index < 0 or index >= array.shape[axis]:
            raise FieldResultArtifactError("Requested time index is outside the stored field.")
        return np.take(array, index, axis=axis)

    def spatial_point_series(self, name: str, spatial_index: tuple[int, ...]) -> np.ndarray:
        array = self.read_series(name)
        manifest = self.read_manifest()
        time_axis = int(manifest["time_axis"])
        spatial_shape = tuple(int(value) for value in manifest["spatial_shape"])
        index = tuple(int(value) for value in spatial_index)
        if len(index) != len(spatial_shape):
            raise FieldResultArtifactError("Spatial index rank does not match the stored field.")
        for value, length in zip(index, spatial_shape, strict=True):
            if value < 0 or value >= length:
                raise FieldResultArtifactError("Requested spatial index is outside the stored field.")
        selector: list[object] = []
        spatial_cursor = 0
        for dimension in range(array.ndim):
            if dimension == time_axis:
                selector.append(slice(None))
            else:
                selector.append(index[spatial_cursor])
                spatial_cursor += 1
        return np.asarray(array[tuple(selector)])

    def exact_point(self, name: str, time_index: int, spatial_index: tuple[int, ...]):
        trace = self.spatial_point_series(name, spatial_index)
        index = int(time_index)
        if index < 0 or index >= trace.shape[0]:
            raise FieldResultArtifactError("Requested time index is outside the stored field.")
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
            raise FieldResultArtifactError("Select one or two distinct spatial display dimensions.")
        if any(value < 0 or value >= len(spatial_shape) for value in display):
            raise FieldResultArtifactError("A spatial display dimension is outside the stored field.")
        fixed = {int(key): int(value) for key, value in (fixed_indices or {}).items()}
        selector: list[object] = []
        for dimension, length in enumerate(spatial_shape):
            if dimension in display:
                selector.append(slice(None))
            else:
                value = fixed.get(dimension, 0)
                if value < 0 or value >= length:
                    raise FieldResultArtifactError("A fixed spatial index is outside the stored field.")
                selector.append(value)
        sliced = np.asarray(spatial[tuple(selector)])
        remaining_order = [dimension for dimension in range(len(spatial_shape)) if dimension in display]
        if remaining_order != list(display) and sliced.ndim == 2:
            sliced = np.transpose(sliced)
        return sliced
