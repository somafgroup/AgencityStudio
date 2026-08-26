"""Structural preflight for AgencityLab 1.1.3 multivariate execution.

Studio validates ownership, exact mappings, finite data and explicit parameter
metadata. It never aligns, rescales, normalizes or aggregates component signals.
AgencityLab remains authoritative for the scientific computation.
"""

from __future__ import annotations

from copy import deepcopy

import numpy as np

from common.units import inspect_unit, units_are_compatible
from systems.models import MemoryWindowMode

from .sources import SourceContractError, column_at
from .validation import PreflightError, validate_parameter_contract, validate_sample_contract

PARAMETER_MODE_SYSTEM_GLOBAL = "SYSTEM_GLOBAL"
PARAMETER_MODE_COMPONENT_VECTOR = "COMPONENT_VECTOR"
WINDOW_MODE_UNSPECIFIED = "UNSPECIFIED"
WINDOW_MODE_SYSTEM_GLOBAL = "SYSTEM_GLOBAL"
WINDOW_MODE_COMPONENT_VECTOR = "COMPONENT_VECTOR"


def _validate_source_column(column: dict, label: str) -> None:
    if column.get("inferred_type") != "NUMERIC":
        raise PreflightError(f"{label} must be numeric for multivariate analysis.")
    if (
        int(column.get("missing_count", 0))
        or int(column.get("non_numeric_count", 0))
        or int(column.get("non_finite_count", 0))
    ):
        raise PreflightError(
            f"{label} contains missing, non-numeric or non-finite values. "
            "Prepare the data explicitly before analysis."
        )


def validate_multivariate_mapping(
    descriptor,
    *,
    coordinate_position: int,
    component_positions,
) -> tuple[dict, list[dict]]:
    """Resolve one coordinate plus ordered component columns without reordering them."""
    coordinate = column_at(descriptor, int(coordinate_position))
    _validate_source_column(coordinate, "The selected coordinate column")
    positions = [int(value) for value in component_positions]
    if not positions:
        raise PreflightError("Select at least one component column.")
    if int(coordinate_position) in positions:
        raise PreflightError("The coordinate column cannot also be a component column.")
    components = []
    for index, position in enumerate(positions, start=1):
        column = column_at(descriptor, position)
        _validate_source_column(column, f"Component {index} column")
        components.append(column)
    return coordinate, components


def _exact_unit(source_unit: str, context_unit: str, label: str) -> list[dict]:
    source = str(source_unit or "").strip()
    context = str(context_unit or "").strip()
    if not source or not context:
        raise PreflightError(f"{label} unit metadata must be explicit before execution.")
    if source == context:
        info = inspect_unit(source)
        if info.recognized:
            return []
        return [
            {
                "code": "UNKNOWN_UNIT",
                "message": f"Unit {source!r} is preserved but Studio cannot dimensionally verify it.",
            }
        ]
    compatible = units_are_compatible(source, context)
    if compatible is True:
        raise PreflightError(
            f"{label} uses {source!r} while the scientific context uses {context!r}. "
            "Studio performs no unit conversion during Analysis; create explicit Prepared Data."
        )
    if compatible is False:
        raise PreflightError(
            f"{label} unit {source!r} is dimensionally incompatible with {context!r}."
        )
    raise PreflightError(
        f"{label} unit labels {source!r} and {context!r} do not match and cannot be verified."
    )


def _explicit_parameter(component: dict, key: str, *, allow_zero: bool = False) -> dict:
    raw = dict(component.get(key) or {})
    try:
        value = float(raw.get("value"))
    except (TypeError, ValueError) as exc:
        raise PreflightError(f"Explicit {key} requires a numeric value for every component.") from exc
    if not np.isfinite(value) or value < 0.0 or (not allow_zero and value == 0.0):
        domain = "non-negative" if allow_zero else "strictly positive"
        raise PreflightError(f"Explicit {key} values must be {domain} and finite.")
    unit = str(raw.get("unit") or "").strip()
    origin = str(raw.get("origin") or "").strip()
    justification = str(raw.get("justification") or "").strip()
    if not unit or not origin or not justification:
        raise PreflightError(
            f"Explicit {key} values require unit, origin and justification for every component."
        )
    return {
        "value": value,
        "value_text": str(raw.get("value_text") or raw.get("value") or value),
        "unit": unit,
        "origin": origin,
        "origin_detail": str(raw.get("origin_detail") or "").strip(),
        "justification": justification,
        "source": "ANALYSIS_OVERRIDE",
    }


def _system_parameter(global_parameters: dict, key: str) -> dict:
    return deepcopy(global_parameters[key])


def resolve_multivariate_parameters(
    *,
    revision,
    component_configs: list[dict],
    a_ref_mode: str,
    tau_mode: str,
    w_mode: str,
    p_c_mode: str,
) -> dict:
    """Resolve the scalar/vector call contract and per-component provenance snapshots."""
    global_parameters = validate_parameter_contract(revision)
    component_count = len(component_configs)
    if component_count == 0:
        raise PreflightError("At least one component is required.")

    for name, mode in (("A_ref", a_ref_mode), ("tau", tau_mode), ("P_c", p_c_mode)):
        if mode not in {PARAMETER_MODE_SYSTEM_GLOBAL, PARAMETER_MODE_COMPONENT_VECTOR}:
            raise PreflightError(f"Unsupported {name} parameter mode.")
    if w_mode not in {
        WINDOW_MODE_UNSPECIFIED,
        WINDOW_MODE_SYSTEM_GLOBAL,
        WINDOW_MODE_COMPONENT_VECTOR,
    }:
        raise PreflightError("Unsupported w parameter mode.")

    resolved: list[dict] = [dict() for _ in component_configs]

    def resolve_regular(key: str, mode: str, *, allow_zero: bool = False):
        if mode == PARAMETER_MODE_SYSTEM_GLOBAL:
            base = _system_parameter(global_parameters, key)
            for target in resolved:
                target[key] = deepcopy(base)
            return base["value"]
        values = []
        for config, target in zip(component_configs, resolved, strict=True):
            item = _explicit_parameter(config, key, allow_zero=allow_zero)
            target[key] = item
            values.append(item["value"])
        return values

    a_ref_call = resolve_regular("A_ref", a_ref_mode)
    tau_call = resolve_regular("tau", tau_mode)
    p_c_call = resolve_regular("P_c", p_c_mode, allow_zero=True)

    if w_mode == WINDOW_MODE_UNSPECIFIED:
        for target in resolved:
            target["w"] = {
                "mode": "UNSPECIFIED",
                "requested_value": None,
                "value_text": "",
                "unit": "",
                "origin": "",
                "origin_detail": "",
                "justification": "",
                "source": "PUBLIC_API_NONE",
            }
        w_call = None
    elif w_mode == WINDOW_MODE_SYSTEM_GLOBAL:
        if revision.w_mode != MemoryWindowMode.EXPLICIT:
            raise PreflightError(
                "The System Revision does not contain an explicit global w. "
                "Choose unspecified w or provide an explicit component vector."
            )
        base = _system_parameter(global_parameters, "w")
        for target in resolved:
            target["w"] = deepcopy(base)
        w_call = base["requested_value"]
    else:
        values = []
        for config, target in zip(component_configs, resolved, strict=True):
            item = _explicit_parameter(config, "w")
            item["mode"] = "EXPLICIT"
            item["requested_value"] = item.pop("value")
            target["w"] = item
            values.append(item["requested_value"])
        w_call = values

    return {
        "call": {
            "A_ref": {"mode": a_ref_mode, "value": a_ref_call},
            "tau": {"mode": tau_mode, "value": tau_call},
            "w": {"mode": w_mode, "value": w_call},
            "P_c": {"mode": p_c_mode, "value": p_c_call},
            "sample_axis": 0,
        },
        "components": resolved,
    }


def validate_multivariate_units(
    *,
    coordinate: dict,
    source_components: list[dict],
    observable_definitions,
    component_parameters: list[dict],
) -> list[dict]:
    warnings: list[dict] = []
    power_units: list[str] = []
    for index, (source, observable, parameters) in enumerate(
        zip(source_components, observable_definitions, component_parameters, strict=True),
        start=1,
    ):
        warnings.extend(
            _exact_unit(source.get("unit", ""), observable.unit, f"Component {index} observable")
        )
        warnings.extend(
            _exact_unit(
                source.get("unit", ""),
                parameters["A_ref"].get("unit", ""),
                f"Component {index} observable/A_ref",
            )
        )
        warnings.extend(
            _exact_unit(
                coordinate.get("unit", ""),
                parameters["tau"].get("unit", ""),
                f"Component {index} coordinate/tau",
            )
        )
        if parameters["w"].get("mode") != "UNSPECIFIED":
            warnings.extend(
                _exact_unit(
                    coordinate.get("unit", ""),
                    parameters["w"].get("unit", ""),
                    f"Component {index} coordinate/w",
                )
            )
        power_units.append(str(parameters["P_c"].get("unit") or "").strip())
    if not power_units or any(not unit for unit in power_units):
        raise PreflightError("P_c unit metadata must be explicit for every component.")
    if len(set(power_units)) != 1:
        raise PreflightError(
            "Component P_c units must match exactly because Studio performs no conversion before "
            "the Lab-provided multivariate aggregation."
        )
    return warnings


def validate_multivariate_samples(
    xi: np.ndarray,
    matrix: np.ndarray,
    *,
    component_parameters: list[dict],
) -> None:
    if matrix.ndim != 2 or matrix.shape[0] != xi.size:
        raise PreflightError(
            "Multivariate source data must be a sample-major two-dimensional matrix sharing xi."
        )
    if matrix.shape[1] != len(component_parameters):
        raise PreflightError("Component parameter count does not match the ordered source matrix.")
    if not np.isfinite(matrix).all():
        raise PreflightError(
            "Multivariate source components must contain only finite values. "
            "Studio will not drop or fill rows."
        )
    for index, parameters in enumerate(component_parameters):
        requested_w = parameters["w"].get("requested_value")
        validate_sample_contract(
            xi,
            matrix[:, index],
            requested_w=requested_w,
            tau=float(parameters["tau"]["value"]),
        )
