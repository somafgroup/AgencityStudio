"""Presentation-only access to immutable canonical Analysis result values.

This module never calls AgencityLab and never reconstructs canonical equations. It
only selects, formats, or derives elementary complex-number representations from
stored result arrays for display.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from django.utils.translation import gettext as _

from .result_reader import AnalysisResultReader


@dataclass(frozen=True)
class SeriesPresentation:
    """UI metadata for one stored canonical result series."""

    key: str
    symbol: str
    group: str
    complex_value: bool = False


SERIES_PRESENTATION: dict[str, SeriesPresentation] = {
    "xi": SeriesPresentation("xi", "ξ", "coordinate"),
    "u": SeriesPresentation("u", "u", "observable"),
    "u_star": SeriesPresentation("u_star", "u*", "observable"),
    "X_star": SeriesPresentation("X_star", "X*", "dynamics"),
    "A_star": SeriesPresentation("A_star", "A*", "dynamics"),
    "t_star": SeriesPresentation("t_star", "t*", "coordinate"),
    "M": SeriesPresentation("M", "M", "structure"),
    "O": SeriesPresentation("O", "O", "structure"),
    "D": SeriesPresentation("D", "D", "dynamics"),
    "S": SeriesPresentation("S", "S", "structure"),
    "J": SeriesPresentation("J", "J", "orientation"),
    "theta": SeriesPresentation("theta", "Θ", "orientation"),
    "U": SeriesPresentation("U", "U", "orientation", complex_value=True),
    "beta": SeriesPresentation("beta", "β", "beta", complex_value=True),
    "b": SeriesPresentation("b", "b", "flux", complex_value=True),
}

SECTION_SERIES: dict[str, tuple[str, ...]] = {
    "observable": ("u", "u_star"),
    "dynamics": ("X_star", "A_star", "D"),
    "structure": ("M", "O", "S"),
    "orientation": ("J", "theta", "U"),
    "beta": ("beta",),
    "flux": ("b",),
}


def _unit_for_series(name: str, manifest: dict) -> str | None:
    units = manifest.get("units") or {}
    if name == "xi":
        return units.get("coordinate") or None
    if name == "u":
        return units.get("observable") or None
    if name == "b":
        return units.get("agencity_flux") or None
    return None


def presentation_registry(reader: AnalysisResultReader) -> dict[str, dict]:
    """Return translated display metadata only for actually stored series."""
    manifest = reader.read_manifest()
    registry: dict[str, dict] = {}
    for name in reader.available_series:
        item = SERIES_PRESENTATION.get(name, SeriesPresentation(name, name, "other"))
        registry[name] = {
            "key": name,
            "symbol": item.symbol,
            "label": _("Structural orientation Θ") if name == "theta" else item.symbol,
            "group": item.group,
            "complex": item.complex_value,
            "unit": _unit_for_series(name, manifest),
            "canonical": True,
        }
    return registry


def _finite_float(value) -> tuple[float | None, str | None]:
    number = float(value)
    if math.isfinite(number):
        return number, None
    if math.isnan(number):
        return None, "nan"
    return None, "positive_infinity" if number > 0 else "negative_infinity"


def _encode_real(value) -> dict:
    number, non_finite = _finite_float(value)
    payload = {"value": number}
    if non_finite:
        payload["non_finite"] = non_finite
    return payload


def _encode_complex(value) -> dict:
    number = complex(value)
    real, real_flag = _finite_float(number.real)
    imag, imag_flag = _finite_float(number.imag)
    magnitude, magnitude_flag = _finite_float(abs(number))
    phase_value = float(np.angle(number))
    phase, phase_flag = _finite_float(phase_value)
    payload = {
        "real": real,
        "imag": imag,
        "magnitude": magnitude,
        "phase": phase,
    }
    flags = {
        key: flag
        for key, flag in {
            "real": real_flag,
            "imag": imag_flag,
            "magnitude": magnitude_flag,
            "phase": phase_flag,
        }.items()
        if flag
    }
    if flags:
        payload["non_finite"] = flags
    return payload


def display_indices(*, start: int, stop: int, max_points: int) -> np.ndarray:
    """Choose display-only original indices while preserving both range endpoints."""
    if start < 0 or stop < start:
        raise IndexError("Invalid visualization range.")
    if max_points <= 0:
        raise ValueError("Display point limit must be positive.")
    count = stop - start
    if count == 0:
        return np.array([], dtype=np.int64)
    if count <= max_points:
        return np.arange(start, stop, dtype=np.int64)
    positions = np.linspace(start, stop - 1, num=max_points, endpoint=True)
    indices = np.unique(np.rint(positions).astype(np.int64))
    if indices[0] != start:
        indices = np.insert(indices, 0, start)
    if indices[-1] != stop - 1:
        indices = np.append(indices, stop - 1)
    return indices


def _coordinate_values(reader: AnalysisResultReader, indices: np.ndarray) -> tuple[str, np.ndarray]:
    if "xi" in reader.available_series:
        return "xi", reader.read_series("xi")[indices]
    return "sample_index", indices.astype(float)


def manifest_payload(reader: AnalysisResultReader, *, result_sha256: str) -> dict:
    """Build the private UI manifest without exposing storage backend details."""
    manifest = reader.read_manifest()
    return {
        "schema_version": manifest.get("schema_version"),
        "format": manifest.get("format"),
        "sample_count": reader.sample_count,
        "series": presentation_registry(reader),
        "units": manifest.get("units") or {},
        "result_context": manifest.get("result_context") or {},
        "agencitylab_version": manifest.get("agencitylab_version"),
        "studio_version": manifest.get("studio_version"),
        "source_sha256": manifest.get("source_sha256"),
        "system_revision_id": manifest.get("system_revision_id"),
        "system_configuration_fingerprint": manifest.get("system_configuration_fingerprint"),
        "execution_fingerprint": manifest.get("execution_fingerprint"),
        "result_sha256": result_sha256,
    }


def series_payload(
    reader: AnalysisResultReader,
    *,
    names: tuple[str, ...],
    start: int,
    stop: int | None,
    max_points: int,
    result_sha256: str,
) -> dict:
    """Return display samples for stored series with original-index preservation."""
    count = reader.sample_count
    resolved_stop = count if stop is None else stop
    if start < 0 or resolved_stop < start or resolved_stop > count:
        raise IndexError("Visualization range is outside the stored result.")
    if not names:
        raise ValueError("At least one stored series is required.")
    for name in names:
        reader.descriptor(name)

    indices = display_indices(start=start, stop=resolved_stop, max_points=max_points)
    coordinate_name, coordinate = _coordinate_values(reader, indices)
    coordinate_points: list[dict] = []
    for original_index, value in zip(indices.tolist(), coordinate, strict=True):
        encoded = _encode_real(value)
        coordinate_points.append({"index": original_index, **encoded})

    registry = presentation_registry(reader)
    output: dict[str, dict] = {}
    for name in names:
        array = reader.read_series(name)
        values = array[indices]
        is_complex = bool(np.iscomplexobj(array))
        points = []
        for original_index, value in zip(indices.tolist(), values, strict=True):
            encoded = _encode_complex(value) if is_complex else _encode_real(value)
            points.append({"index": original_index, **encoded})
        output[name] = {
            "metadata": registry.get(name, {"key": name, "symbol": name, "complex": is_complex}),
            "dtype": str(array.dtype),
            "shape": list(array.shape),
            "points": points,
            "display_derivations": ["real", "imag", "magnitude", "phase"] if is_complex else [],
        }

    return {
        "result_sha256": result_sha256,
        "sample_count": count,
        "range": {"start": start, "stop": resolved_stop},
        "display_count": int(indices.size),
        "decimated": int(indices.size) < (resolved_stop - start),
        "coordinate": {"name": coordinate_name, "points": coordinate_points},
        "series": output,
    }


def sample_payload(reader: AnalysisResultReader, *, index: int, result_sha256: str) -> dict:
    """Return exact full-resolution values for one original sample index."""
    values = reader.read_sample(index)
    registry = presentation_registry(reader)
    encoded: dict[str, dict] = {}
    for name, value in values.items():
        is_complex = bool(np.iscomplexobj(value))
        encoded[name] = {
            "metadata": registry.get(name, {"key": name, "symbol": name, "complex": is_complex}),
            "value": _encode_complex(value) if is_complex else _encode_real(value),
        }
    coordinate = encoded.get("xi")
    return {
        "result_sha256": result_sha256,
        "index": index,
        "display_index": index + 1,
        "sample_count": reader.sample_count,
        "coordinate": coordinate,
        "values": encoded,
    }


def exact_table_payload(
    reader: AnalysisResultReader,
    *,
    start: int,
    stop: int,
    result_sha256: str,
) -> dict:
    """Return exact, non-decimated table rows in original result order."""
    if start < 0 or stop < start or stop > reader.sample_count:
        raise IndexError("Table range is outside the stored result.")
    names = reader.available_series
    arrays = {name: reader.read_series_range(name, start=start, stop=stop) for name in names}
    registry = presentation_registry(reader)
    rows: list[dict] = []
    for offset in range(stop - start):
        index = start + offset
        cells: list[dict] = []
        for name in names:
            value = arrays[name][offset]
            is_complex = bool(np.iscomplexobj(value))
            cells.append(
                {
                    "key": name,
                    "symbol": registry[name]["symbol"],
                    "complex": is_complex,
                    "value": _encode_complex(value) if is_complex else _encode_real(value),
                }
            )
        rows.append({"index": index, "display_index": index + 1, "cells": cells})
    return {
        "result_sha256": result_sha256,
        "sample_count": reader.sample_count,
        "start": start,
        "stop": stop,
        "series": [registry[name] for name in names],
        "rows": rows,
    }
