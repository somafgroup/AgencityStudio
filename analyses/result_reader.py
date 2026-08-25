"""Read-only, schema-aware access to immutable canonical Analysis result artifacts."""

from __future__ import annotations

import copy
import json
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from typing import BinaryIO, Self

import numpy as np

from .results import RESULT_FORMAT, RESULT_SCHEMA_VERSION, ResultArtifactError


@dataclass(frozen=True)
class ResultSeriesDescriptor:
    """Manifest-backed description of one stored numerical series."""

    name: str
    shape: tuple[int, ...]
    dtype: str


class AnalysisResultReader:
    """Read canonical result arrays without rewriting or recomputing scientific values.

    The reader validates the stored manifest and each requested ``.npy`` payload. It
    deliberately exposes only read operations. Range and sample access may still
    decompress the requested NumPy member because ZIP_NPY_JSON schema v1 stores one
    compressed ``.npy`` member per series, but unrelated series are not loaded.
    """

    def __init__(self, handle: BinaryIO, *, expected_run_id: str | None = None) -> None:
        self._handle = handle
        try:
            self._archive = zipfile.ZipFile(handle, "r")
            self._manifest = json.loads(self._archive.read("manifest.json"))
        except (OSError, ValueError, zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
            raise ResultArtifactError("Stored analysis result is unavailable or corrupt.") from exc

        if self._manifest.get("schema_version") != RESULT_SCHEMA_VERSION:
            self.close()
            raise ResultArtifactError("Unsupported analysis result schema version.")
        if self._manifest.get("format") != RESULT_FORMAT:
            self.close()
            raise ResultArtifactError("Unsupported analysis result format.")
        if expected_run_id and self._manifest.get("run_id") != str(expected_run_id):
            self.close()
            raise ResultArtifactError("Stored result belongs to a different AnalysisRun.")

        self._inventory: dict[str, ResultSeriesDescriptor] = {}
        try:
            for item in self._manifest.get("series", []):
                descriptor = ResultSeriesDescriptor(
                    name=str(item["name"]),
                    shape=tuple(int(value) for value in item["shape"]),
                    dtype=str(item["dtype"]),
                )
                if descriptor.name in self._inventory:
                    raise ResultArtifactError("Stored result manifest contains duplicate series.")
                self._inventory[descriptor.name] = descriptor
        except (KeyError, TypeError, ValueError) as exc:
            self.close()
            if isinstance(exc, ResultArtifactError):
                raise
            raise ResultArtifactError("Stored result manifest is invalid.") from exc

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        archive = getattr(self, "_archive", None)
        if archive is not None:
            archive.close()
            self._archive = None

    def read_manifest(self) -> dict:
        """Return an in-memory copy of the immutable stored manifest."""
        return copy.deepcopy(self._manifest)

    @property
    def available_series(self) -> tuple[str, ...]:
        return tuple(self._inventory)

    def descriptor(self, name: str) -> ResultSeriesDescriptor:
        try:
            return self._inventory[name]
        except KeyError as exc:
            raise KeyError(f"Stored result does not contain series {name!r}.") from exc

    @property
    def sample_count(self) -> int:
        """Return the first-axis sample count without loading numerical arrays."""
        preferred = self._inventory.get("xi") or self._inventory.get("u")
        if preferred is None:
            preferred = next(iter(self._inventory.values()), None)
        if preferred is None or not preferred.shape:
            return 0
        return preferred.shape[0]

    def read_series(self, name: str) -> np.ndarray:
        """Load exactly one stored series and validate shape/dtype against the manifest."""
        descriptor = self.descriptor(name)
        try:
            with self._archive.open(f"arrays/{name}.npy", "r") as member:
                array = np.load(member, allow_pickle=False)
        except (OSError, ValueError, KeyError) as exc:
            raise ResultArtifactError(f"Stored series {name} is unavailable or corrupt.") from exc

        if tuple(array.shape) != descriptor.shape or str(array.dtype) != descriptor.dtype:
            raise ResultArtifactError(f"Stored series {name} does not match its manifest.")
        return array

    def _validate_bounds(self, start: int, stop: int | None) -> tuple[int, int]:
        count = self.sample_count
        if start < 0:
            raise IndexError("Result range start cannot be negative.")
        resolved_stop = count if stop is None else stop
        if resolved_stop < start or resolved_stop > count:
            raise IndexError("Result range is outside the stored sample bounds.")
        return start, resolved_stop

    def read_series_range(self, name: str, *, start: int = 0, stop: int | None = None) -> np.ndarray:
        """Return an exact first-axis slice of one stored series."""
        start, stop = self._validate_bounds(start, stop)
        array = self.read_series(name)
        if array.ndim == 0:
            raise ResultArtifactError(f"Stored series {name} has no sample axis.")
        return array[start:stop]

    def read_sample(self, index: int, names: Iterable[str] | None = None) -> dict[str, np.generic | np.ndarray]:
        """Return exact stored values for one original sample index."""
        count = self.sample_count
        if index < 0 or index >= count:
            raise IndexError("Sample index is outside the stored result.")
        selected = tuple(names) if names is not None else self.available_series
        values: dict[str, np.generic | np.ndarray] = {}
        for name in selected:
            array = self.read_series(name)
            if array.ndim == 0 or array.shape[0] <= index:
                raise ResultArtifactError(f"Stored series {name} cannot provide the requested sample.")
            values[name] = array[index]
        return values
