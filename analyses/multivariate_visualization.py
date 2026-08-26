"""Presentation adapters for immutable Lab-provided multivariate results.

The adapters expose stored component or aggregate series through the existing Plan
8 presentation functions. They never compute a scientific aggregate or modify a
stored value.
"""

from __future__ import annotations

import copy

from .visualization import exact_table_payload, manifest_payload, sample_payload, series_payload


class ComponentResultAdapter:
    """Read one stored Lab component through the canonical visualization protocol."""

    def __init__(self, reader, *, position: int, coordinate_unit: str = "") -> None:
        self.reader = reader
        self.position = int(position)
        self._manifest = reader.read_manifest()
        component = next(
            item
            for item in self._manifest.get("components", [])
            if int(item["position"]) == self.position
        )
        self.component = component
        self.available_series = reader.component_series(self.position)
        self._visual_manifest = {
            **self._manifest,
            "units": {
                "observable": component.get("unit", ""),
                "coordinate": coordinate_unit,
                "power": (component.get("parameter_snapshot") or {}).get("P_c", {}).get(
                    "unit", ""
                ),
                "agencity_flux": (component.get("parameter_snapshot") or {}).get(
                    "P_c", {}
                ).get("unit", ""),
            },
            "result_context": component.get("lab_context") or {},
        }

    @property
    def sample_count(self) -> int:
        return self.reader.sample_count

    def read_manifest(self) -> dict:
        return copy.deepcopy(self._visual_manifest)

    def descriptor(self, name: str):
        if name not in self.available_series:
            raise KeyError(name)
        array = self.reader.read_component(self.position, name)

        class Descriptor:
            shape = array.shape
            dtype = str(array.dtype)

        return Descriptor()

    def read_series(self, name: str):
        return self.reader.read_component(self.position, name)

    def read_series_range(self, name: str, *, start: int = 0, stop: int | None = None):
        return self.reader.read_component_range(
            self.position,
            name,
            start=start,
            stop=stop,
        )

    def read_sample(self, index: int, names=None):
        selected = tuple(names) if names is not None else self.available_series
        return {
            name: self.reader.read_component(self.position, name)[index]
            for name in selected
        }


class AggregateResultAdapter:
    """Expose only one-dimensional aggregate series returned directly by Lab."""

    DISPLAY_SERIES = ("xi", "P_c_total", "beta_multi", "beta_multi_defined", "b_total")

    def __init__(self, reader, *, coordinate_unit: str = "", power_unit: str = "") -> None:
        self.reader = reader
        self._manifest = reader.read_manifest()
        self.available_series = tuple(
            name for name in self.DISPLAY_SERIES if name in reader.aggregate_series
        )
        self._visual_manifest = {
            **self._manifest,
            "units": {
                "coordinate": coordinate_unit,
                "power": power_unit,
                "agencity_flux": power_unit,
            },
            "result_context": {
                "aggregation": self._manifest.get("aggregation"),
                "scientific_boundary": self._manifest.get("scientific_boundary"),
            },
        }

    @property
    def sample_count(self) -> int:
        return self.reader.sample_count

    def read_manifest(self) -> dict:
        return copy.deepcopy(self._visual_manifest)

    def descriptor(self, name: str):
        if name not in self.available_series:
            raise KeyError(name)
        array = self.reader.read_aggregate(name)

        class Descriptor:
            shape = array.shape
            dtype = str(array.dtype)

        return Descriptor()

    def read_series(self, name: str):
        if name not in self.available_series:
            raise KeyError(name)
        return self.reader.read_aggregate(name)

    def read_series_range(self, name: str, *, start: int = 0, stop: int | None = None):
        if name not in self.available_series:
            raise KeyError(name)
        return self.reader.read_aggregate_range(name, start=start, stop=stop)

    def read_sample(self, index: int, names=None):
        selected = tuple(names) if names is not None else self.available_series
        return {name: self.read_series(name)[index] for name in selected}


def component_manifest_payload(adapter, *, result_sha256: str) -> dict:
    payload = manifest_payload(adapter, result_sha256=result_sha256)
    payload["component"] = copy.deepcopy(adapter.component)
    payload["scientific_status"] = adapter.read_manifest().get("scientific_status")
    return payload


def component_series_payload(adapter, **kwargs) -> dict:
    return series_payload(adapter, **kwargs)


def component_sample_payload(adapter, **kwargs) -> dict:
    return sample_payload(adapter, **kwargs)


def component_table_payload(adapter, **kwargs) -> dict:
    return exact_table_payload(adapter, **kwargs)


def _mark_aggregate(payload: dict) -> dict:
    for item in (payload.get("series") or {}).values():
        metadata = item.get("metadata") or {}
        metadata["canonical"] = False
    for item in payload.get("values") or {}:
        metadata = (payload["values"][item].get("metadata") or {})
        metadata["canonical"] = False
    return payload


def aggregate_manifest_payload(adapter, *, result_sha256: str) -> dict:
    payload = manifest_payload(adapter, result_sha256=result_sha256)
    manifest = adapter.read_manifest()
    for metadata in (payload.get("series") or {}).values():
        metadata["canonical"] = False
    payload["aggregation"] = manifest.get("aggregation")
    payload["scientific_boundary"] = manifest.get("scientific_boundary")
    payload["scientific_status"] = manifest.get("scientific_status")
    return payload


def aggregate_series_payload(adapter, **kwargs) -> dict:
    return _mark_aggregate(series_payload(adapter, **kwargs))


def aggregate_sample_payload(adapter, **kwargs) -> dict:
    return _mark_aggregate(sample_payload(adapter, **kwargs))


def aggregate_table_payload(adapter, **kwargs) -> dict:
    payload = exact_table_payload(adapter, **kwargs)
    for metadata in payload.get("series") or []:
        metadata["canonical"] = False
    return payload
