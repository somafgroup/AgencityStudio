"""Web-safe read-only payloads for immutable sensitivity results."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .models import StudyType


def _safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return _safe(value.item())
    if isinstance(value, complex):
        return {
            "real": _safe(float(value.real)),
            "imag": _safe(float(value.imag)),
            "magnitude": _safe(float(abs(value))),
        }
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, np.ndarray):
        return [_safe(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    return value


def available_metrics(study, stored) -> tuple[str, ...]:
    if study.study_type == StudyType.TAU_MULTISCALE:
        preferred = ("b_mean", "b_rms", "beta_mean", "J_mean", "S_mean")
    else:
        preferred = ("phi2", "phi1_mean_abs_contrast")
    return tuple(name for name in preferred if name in stored.arrays)


def manifest_payload(study, stored) -> dict:
    scale_name = "tau" if study.study_type == StudyType.TAU_MULTISCALE else "candidate_w"
    effective = stored.arrays.get(scale_name, np.asarray([], dtype=float))
    return {
        "study_id": str(study.pk),
        "study_type": study.study_type,
        "status": study.status,
        "scientific_status": study.scientific_status,
        "grid_unit": study.grid_unit,
        "requested_grid": _safe(study.requested_grid),
        "effective_grid": _safe(effective),
        "effective_w": _safe(stored.arrays.get("w", np.asarray([], dtype=float))),
        "metrics": list(available_metrics(study, stored)),
        "scalars": _safe(stored.scalars),
        "result_sha256": study.result_sha256,
        "canonical_result_sha256": study.canonical_result_sha256,
    }


def chart_payload(study, stored, *, metric: str | None = None) -> dict:
    metrics = available_metrics(study, stored)
    if not metrics:
        return {"points": [], "metric": None}
    selected = metric if metric in metrics else metrics[0]
    scale_name = "tau" if study.study_type == StudyType.TAU_MULTISCALE else "candidate_w"
    scales = np.asarray(stored.arrays[scale_name])
    values = np.asarray(stored.arrays[selected])
    points = [
        {"index": index, "scale": _safe(scales[index]), "value": _safe(values[index])}
        for index in range(len(scales))
    ]
    return {
        "metric": selected,
        "points": points,
        "grid_unit": study.grid_unit,
        "scale_symbol": "tau" if study.study_type == StudyType.TAU_MULTISCALE else "w",
        "display_only": True,
        "result_sha256": study.result_sha256,
    }


def table_rows(study, stored) -> list[dict]:
    metrics = available_metrics(study, stored)
    scale_name = "tau" if study.study_type == StudyType.TAU_MULTISCALE else "candidate_w"
    scales = np.asarray(stored.arrays.get(scale_name, []))
    rows = []
    for index in range(len(scales)):
        values = {name: _safe(np.asarray(stored.arrays[name])[index]) for name in metrics}
        if study.study_type == StudyType.TAU_MULTISCALE and "w" in stored.arrays:
            values["effective_w"] = _safe(np.asarray(stored.arrays["w"])[index])
        if study.study_type == StudyType.W_SENSITIVITY and "eligible" in stored.arrays:
            values["eligible"] = bool(np.asarray(stored.arrays["eligible"])[index])
        rows.append({"index": index, "scale": _safe(scales[index]), "values": values})
    return rows
