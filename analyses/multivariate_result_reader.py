"""Schema-aware read-only access to immutable multivariate result artifacts."""

from __future__ import annotations

import copy
import json
import zipfile
from dataclasses import dataclass
from typing import BinaryIO, Self

import numpy as np

from .multivariate_results import (
    MULTIVARIATE_RESULT_FORMAT,
    MULTIVARIATE_RESULT_SCHEMA_VERSION,
    MultivariateResultArtifactError,
)


@dataclass(frozen=True)
class MultivariateSeriesDescriptor:
    name: str
    shape: tuple[int, ...]
    dtype: str
    member: str


class MultivariateResultReader:
    """Read Lab-provided multivariate arrays lazily without scientific recomputation."""

    def __init__(self, handle: BinaryIO, *, expected_run_id: str | None = None) -> None:
        self._handle = handle
        try:
            self._archive = zipfile.ZipFile(handle, "r")
            self._manifest = json.loads(self._archive.read("manifest.json"))
        except (OSError, ValueError, zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
            raise MultivariateResultArtifactError(
                "Stored multivariate result is unavailable or corrupt."
            ) from exc
        if self._manifest.get("schema_version") != MULTIVARIATE_RESULT_SCHEMA_VERSION:
            self.close()
            raise MultivariateResultArtifactError("Unsupported multivariate result schema version.")
        if self._manifest.get("format") != MULTIVARIATE_RESULT_FORMAT:
            self.close()
            raise MultivariateResultArtifactError("Unsupported multivariate result format.")
        if expected_run_id and self._manifest.get("run_id") != str(expected_run_id):
            self.close()
            raise MultivariateResultArtifactError(
                "Stored multivariate result belongs to a different AnalysisRun."
            )
        self._aggregate = self._inventory(self._manifest.get("aggregate_series") or [])
        self._components: dict[int, dict[str, MultivariateSeriesDescriptor]] = {}
        for component in self._manifest.get("components") or []:
            position = int(component["position"])
            if position in self._components:
                self.close()
                raise MultivariateResultArtifactError(
                    "Stored multivariate manifest contains duplicate component positions."
                )
            self._components[position] = self._inventory(component.get("series") or [])

    @staticmethod
    def _inventory(items) -> dict[str, MultivariateSeriesDescriptor]:
        inventory: dict[str, MultivariateSeriesDescriptor] = {}
        try:
            for item in items:
                descriptor = MultivariateSeriesDescriptor(
                    name=str(item["name"]),
                    shape=tuple(int(value) for value in item["shape"]),
                    dtype=str(item["dtype"]),
                    member=str(item["member"]),
                )
                if descriptor.name in inventory:
                    raise MultivariateResultArtifactError(
                        "Stored multivariate manifest contains duplicate series."
                    )
                inventory[descriptor.name] = descriptor
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, MultivariateResultArtifactError):
                raise
            raise MultivariateResultArtifactError("Stored multivariate manifest is invalid.") from exc
        return inventory

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
        return copy.deepcopy(self._manifest)

    @property
    def component_positions(self) -> tuple[int, ...]:
        return tuple(sorted(self._components))

    @property
    def aggregate_series(self) -> tuple[str, ...]:
        return tuple(self._aggregate)

    def component_series(self, position: int) -> tuple[str, ...]:
        try:
            return tuple(self._components[int(position)])
        except KeyError as exc:
            raise KeyError(f"Stored result does not contain component {position}.") from exc

    def _read(self, descriptor: MultivariateSeriesDescriptor) -> np.ndarray:
        try:
            with self._archive.open(descriptor.member, "r") as member:
                array = np.load(member, allow_pickle=False)
        except (OSError, ValueError, KeyError) as exc:
            raise MultivariateResultArtifactError(
                f"Stored multivariate series {descriptor.name!r} is unavailable or corrupt."
            ) from exc
        if tuple(array.shape) != descriptor.shape or str(array.dtype) != descriptor.dtype:
            raise MultivariateResultArtifactError(
                f"Stored multivariate series {descriptor.name!r} does not match its manifest."
            )
        return array

    def read_aggregate(self, name: str) -> np.ndarray:
        try:
            descriptor = self._aggregate[name]
        except KeyError as exc:
            raise KeyError(f"Stored result does not contain aggregate series {name!r}.") from exc
        return self._read(descriptor)

    def read_component(self, position: int, name: str) -> np.ndarray:
        try:
            descriptor = self._components[int(position)][name]
        except KeyError as exc:
            raise KeyError(
                f"Stored result does not contain series {name!r} for component {position}."
            ) from exc
        return self._read(descriptor)

    @property
    def sample_count(self) -> int:
        descriptor = self._aggregate.get("xi")
        if descriptor is None and self._components:
            descriptor = next(iter(self._components[min(self._components)].values()), None)
        if descriptor is None or not descriptor.shape:
            return 0
        return descriptor.shape[-1] if descriptor.name in {"beta_components", "b_components", "P_c_components"} else descriptor.shape[0]

    def read_aggregate_range(self, name: str, *, start: int = 0, stop: int | None = None) -> np.ndarray:
        array = self.read_aggregate(name)
        count = self.sample_count
        resolved_stop = count if stop is None else int(stop)
        if start < 0 or resolved_stop < start or resolved_stop > count:
            raise IndexError("Multivariate result range is outside stored sample bounds.")
        if array.ndim == 1 and array.shape[0] == count:
            return array[start:resolved_stop]
        if array.ndim >= 2 and array.shape[-1] == count:
            return array[..., start:resolved_stop]
        raise MultivariateResultArtifactError(f"Aggregate series {name!r} has no sample axis.")

    def read_component_range(
        self,
        position: int,
        name: str,
        *,
        start: int = 0,
        stop: int | None = None,
    ) -> np.ndarray:
        array = self.read_component(position, name)
        count = self.sample_count
        resolved_stop = count if stop is None else int(stop)
        if start < 0 or resolved_stop < start or resolved_stop > count:
            raise IndexError("Multivariate result range is outside stored sample bounds.")
        if array.ndim == 0 or array.shape[0] != count:
            raise MultivariateResultArtifactError(f"Component series {name!r} has no sample axis.")
        return array[start:resolved_stop]

    def read_sample(self, index: int) -> dict:
        count = self.sample_count
        if index < 0 or index >= count:
            raise IndexError("Sample index is outside the stored multivariate result.")
        aggregate = {}
        for name in self.aggregate_series:
            array = self.read_aggregate(name)
            if array.ndim == 1 and array.shape[0] == count:
                aggregate[name] = array[index]
            elif array.ndim >= 2 and array.shape[-1] == count:
                aggregate[name] = array[..., index]
        components = {}
        for position in self.component_positions:
            values = {}
            for name in self.component_series(position):
                array = self.read_component(position, name)
                if array.ndim > 0 and array.shape[0] == count:
                    values[name] = array[index]
            components[position] = values
        return {"aggregate": aggregate, "components": components}
