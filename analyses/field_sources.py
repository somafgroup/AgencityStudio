"""Exact N-dimensional source materialization for immutable field Runs."""

from __future__ import annotations

from dataclasses import dataclass

from datasets.field_source import FieldSourceError, load_npz_arrays

from .field_contract import (
    PARAMETER_MODE_SCALAR,
    SPATIAL_AXES_EXPLICIT,
    WINDOW_MODE_UNSPECIFIED,
)


@dataclass(frozen=True)
class MaterializedFieldInputs:
    u: object
    t: object
    spatial_axes: tuple | None
    A_ref: object
    tau: object
    w: object | None
    P_c: object
    time_axis: int


def _parameter_value(snapshot: dict, arrays: dict):
    if snapshot.get("mode") == PARAMETER_MODE_SCALAR:
        return float(snapshot["value"])
    return arrays[snapshot["array_key"]]


def materialize_field_run(run) -> MaterializedFieldInputs:
    """Load the exact arrays identified by an immutable field Run snapshot."""

    version = run.source_dataset_version
    if version is None:
        raise FieldSourceError("Observable field Runs require a raw immutable NPZ Dataset Version.")
    if version.source_sha256 != run.source_sha256:
        raise FieldSourceError("The pinned field source SHA-256 no longer matches the Run.")
    mapping = dict(run.mapping_snapshot or {})
    parameters = dict(run.parameter_snapshot or {})
    keys = [mapping["u"]["key"], mapping["time"]["key"]]
    if mapping.get("spatial_axes_mode") == SPATIAL_AXES_EXPLICIT:
        keys.extend(axis["array_key"] for axis in mapping.get("spatial_axes", []))
    for name in ("A_ref", "tau", "w", "P_c"):
        snapshot = parameters[name]
        if snapshot.get("array_key"):
            keys.append(snapshot["array_key"])
    arrays = load_npz_arrays(version, keys)
    if mapping.get("spatial_axes_mode") == SPATIAL_AXES_EXPLICIT:
        spatial_axes = tuple(arrays[axis["array_key"]] for axis in mapping["spatial_axes"])
    else:
        spatial_axes = None
    w_snapshot = parameters["w"]
    if w_snapshot.get("mode") == WINDOW_MODE_UNSPECIFIED:
        w_value = None
    elif w_snapshot.get("mode") == PARAMETER_MODE_SCALAR:
        w_value = float(w_snapshot.get("requested_value", w_snapshot["value"]))
    else:
        w_value = arrays[w_snapshot["array_key"]]
    return MaterializedFieldInputs(
        u=arrays[mapping["u"]["key"]],
        t=arrays[mapping["time"]["key"]],
        spatial_axes=spatial_axes,
        A_ref=_parameter_value(parameters["A_ref"], arrays),
        tau=_parameter_value(parameters["tau"], arrays),
        w=w_value,
        P_c=_parameter_value(parameters["P_c"], arrays),
        time_axis=int(mapping["time"]["time_axis"]),
    )
