"""Presentation-only payloads for immutable AgencityLab diagnostic reports."""

from . import result_reader
from . import visualization


DIAGNOSTIC_SERIES = {
    "sigma_theta": {
        "key": "sigma_theta",
        "symbol": "ΣΘ",
        "label": "Angular variance Sigma_Theta",
        "group": "coherence",
        "complex": False,
        "unit": None,
        "canonical": False,
        "scientific_status": "DIAGNOSTIC / theory-derived",
    },
    "curvature": {
        "key": "curvature",
        "symbol": "κ",
        "label": "Beta trajectory curvature",
        "group": "geometry",
        "complex": False,
        "unit": None,
        "canonical": False,
        "scientific_status": "DIAGNOSTIC",
    },
    "local_real_agencity": {
        "key": "local_real_agencity",
        "symbol": "local criterion",
        "label": "Local real-agencity criterion",
        "group": "real_agencity",
        "complex": False,
        "unit": None,
        "canonical": False,
        "scientific_status": "DIAGNOSTIC / configured criterion",
    },
}


def _interval(report: dict) -> tuple[int, int]:
    interval = dict(report.get("analysis_interval") or {})
    start = int(interval.get("start_index", 0) or 0)
    stop = int(interval.get("stop_index", start) or start)
    return start, stop


def _series_values(report: dict, name: str, sample_count: int) -> tuple[int, list] | None:
    if name == "sigma_theta":
        values = (
            report.get("coherence", {})
            .get("structural_orientation", {})
            .get("sigma_theta")
        )
        if isinstance(values, list) and len(values) == sample_count:
            return 0, values
        return None
    if name == "curvature":
        values = report.get("geometry", {}).get("curvature")
        start, stop = _interval(report)
        if isinstance(values, list) and stop - start == len(values):
            return start, values
        return None
    if name == "local_real_agencity":
        values = report.get("real_agencity", {}).get("local_real_agencity")
        start, stop = _interval(report)
        if isinstance(values, list) and stop - start == len(values):
            return start, values
        return None
    return None


def diagnostic_series_inventory(report: dict, sample_count: int) -> dict[str, dict]:
    inventory: dict[str, dict] = {}
    for name, metadata in DIAGNOSTIC_SERIES.items():
        if _series_values(report, name, sample_count) is not None:
            inventory[name] = dict(metadata)
    return inventory


def diagnostic_manifest_payload(
    canonical_reader: result_reader.AnalysisResultReader,
    *,
    report: dict,
    diagnostic_result_sha256: str,
    canonical_result_sha256: str,
    diagnostic_run,
) -> dict:
    return {
        "schema_version": diagnostic_run.diagnostic_schema_version,
        "format": "ZIP_JSON",
        "sample_count": canonical_reader.sample_count,
        "series": diagnostic_series_inventory(report, canonical_reader.sample_count),
        "result_sha256": diagnostic_result_sha256,
        "canonical_result_sha256": canonical_result_sha256,
        "agencitylab_version": diagnostic_run.agencitylab_version,
        "studio_version": diagnostic_run.studio_version,
        "diagnostic_execution_fingerprint": diagnostic_run.execution_fingerprint,
    }


def diagnostic_series_payload(
    canonical_reader: result_reader.AnalysisResultReader,
    *,
    report: dict,
    names: tuple[str, ...],
    start: int,
    stop: int | None,
    max_points: int,
    diagnostic_result_sha256: str,
) -> dict:
    count = canonical_reader.sample_count
    resolved_stop = count if stop is None else stop
    if start < 0 or resolved_stop < start or resolved_stop > count:
        raise IndexError("Diagnostic visualization range is outside the canonical result.")
    inventory = diagnostic_series_inventory(report, count)
    if not names:
        raise ValueError("At least one available diagnostic series is required.")
    for name in names:
        if name not in inventory:
            raise KeyError(f"Diagnostic result does not contain series {name!r}.")

    indices = visualization.display_indices(
        start=start,
        stop=resolved_stop,
        max_points=max_points,
    )
    xi = (
        canonical_reader.read_series("xi")[indices]
        if "xi" in canonical_reader.available_series
        else indices.astype(float)
    )
    coordinate = [
        {"index": int(index), **visualization._encode_real(value)}
        for index, value in zip(indices.tolist(), xi, strict=True)
    ]

    output: dict[str, dict] = {}
    for name in names:
        offset, values = _series_values(report, name, count) or (0, [])
        points = []
        for index in indices.tolist():
            local = index - offset
            if local < 0 or local >= len(values):
                encoded = visualization._encode_real(float("nan"))
            else:
                value = values[local]
                if isinstance(value, bool):
                    value = 1.0 if value else 0.0
                encoded = visualization._encode_real(value)
            points.append({"index": int(index), **encoded})
        output[name] = {
            "metadata": inventory[name],
            "dtype": "diagnostic-json",
            "shape": [count],
            "points": points,
            "display_derivations": [],
        }

    return {
        "result_sha256": diagnostic_result_sha256,
        "sample_count": count,
        "range": {"start": start, "stop": resolved_stop},
        "display_count": int(indices.size),
        "decimated": int(indices.size) < (resolved_stop - start),
        "coordinate": {"name": "xi", "points": coordinate},
        "series": output,
    }


def diagnostic_sample_payload(
    canonical_reader: result_reader.AnalysisResultReader,
    *,
    report: dict,
    index: int,
    diagnostic_result_sha256: str,
) -> dict:
    """Return exact canonical values plus diagnostic values at one original index."""
    payload = visualization.sample_payload(
        canonical_reader,
        index=index,
        result_sha256=diagnostic_result_sha256,
    )
    inventory = diagnostic_series_inventory(report, canonical_reader.sample_count)
    for name, metadata in inventory.items():
        offset, values = _series_values(report, name, canonical_reader.sample_count) or (0, [])
        local = index - offset
        if local < 0 or local >= len(values):
            continue
        value = values[local]
        if isinstance(value, bool):
            value = 1.0 if value else 0.0
        payload["values"][name] = {
            "metadata": metadata,
            "value": visualization._encode_real(value),
        }
    payload["diagnostic"] = True
    return payload
