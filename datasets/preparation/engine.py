"""Deterministic explicit tabular transformations for prepared-data artifacts.

This module is deliberately upstream of AgencityLab. It performs only transformations
that a user explicitly requests and never derives A_ref, tau, w, P_c, beta, or b.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from django.conf import settings
from pint import DimensionalityError, UndefinedUnitError, UnitRegistry

from datasets.importers import get_importer
from datasets.importers.base import ImporterError, TabularSource
from datasets.inspection import inspect_table
from datasets.models import DatasetImportStatus
from datasets.storage import dataset_storage

ENGINE_ID = "studio.tabular-preparation"
ENGINE_VERSION = "1"

OPERATION_LABELS = {
    "time_crop": "Time range",
    "row_range": "Row range",
    "exclude_rows": "Exclude rows",
    "missing_values": "Missing values",
    "resample": "Resample",
    "moving_average": "Moving average",
    "unit_conversion": "Unit conversion",
    "select_columns": "Select columns",
    "sort_time": "Sort by time",
}

_UREG = UnitRegistry(autoconvert_offset_to_baseunit=True)


class PreparationError(ValueError):
    """Expected, user-facing preparation failure without traceback leakage."""


@dataclass
class PreparedTable:
    """In-memory execution representation for one bounded preparation task.

    Column references use the original DatasetColumn position as ``source_position`` so
    recipe references remain stable even after a column-selection step.
    """

    rows: list[list[object]]
    columns: list[dict[str, Any]]
    decimal_separator: str = "."

    def column_index(self, source_position: int) -> int:
        for index, column in enumerate(self.columns):
            if int(column["source_position"]) == int(source_position):
                return index
        raise PreparationError(f"Column {source_position} is not available at this recipe step.")

    def column(self, source_position: int) -> dict[str, Any]:
        return self.columns[self.column_index(source_position)]

    def reindex(self) -> None:
        for position, column in enumerate(self.columns, 1):
            column["position"] = position

    def metadata_snapshot(self) -> list[dict[str, Any]]:
        self.reindex()
        return [copy.deepcopy(column) for column in self.columns]


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (float, np.floating)) and math.isnan(float(value)):
        return True
    if isinstance(value, str):
        try:
            return math.isnan(float(value.strip()))
        except ValueError:
            return False
    return False


def _parse_number(value: object, decimal_separator: str) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if decimal_separator == ",":
        if "." in text:
            return None
        text = text.replace(",", ".")
    elif "," in text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _time_value(value: object, decimal_separator: str) -> tuple[str, float, datetime | None]:
    number = _parse_number(value, decimal_separator)
    if number is not None and math.isfinite(number):
        return "numeric", number, None
    parsed = _parse_datetime(value)
    if parsed is None:
        raise PreparationError("The selected time column contains unreadable or non-finite values.")
    if parsed.tzinfo is not None:
        return "datetime-aware", parsed.timestamp(), parsed
    scalar = (
        parsed.toordinal() * 86400
        + parsed.hour * 3600
        + parsed.minute * 60
        + parsed.second
        + parsed.microsecond / 1_000_000
    )
    return "datetime-naive", scalar, parsed


def _time_series(
    table: PreparedTable,
    source_position: int,
) -> tuple[str, np.ndarray, list[datetime | None]]:
    index = table.column_index(source_position)
    mode: str | None = None
    scalars: list[float] = []
    datetimes: list[datetime | None] = []
    for row in table.rows:
        value_mode, scalar, parsed = _time_value(row[index], table.decimal_separator)
        if mode is None:
            mode = value_mode
        elif mode != value_mode:
            raise PreparationError("The selected time column mixes incompatible representations.")
        scalars.append(scalar)
        datetimes.append(parsed)
    if mode is None:
        raise PreparationError("The selected time column contains no values.")
    return mode, np.asarray(scalars, dtype=float), datetimes


def _strictly_increasing(values: np.ndarray) -> bool:
    return len(values) < 2 or bool(np.all(np.diff(values) > 0))


def _numeric_vector(table: PreparedTable, source_position: int) -> np.ndarray:
    index = table.column_index(source_position)
    values: list[float] = []
    for row in table.rows:
        raw = row[index]
        if _is_missing(raw):
            values.append(float("nan"))
            continue
        number = _parse_number(raw, table.decimal_separator)
        if number is None:
            raise PreparationError(
                f"Column {source_position} contains non-numeric values and cannot be transformed numerically."
            )
        values.append(number)
    return np.asarray(values, dtype=float)


def _column_positions(value: object) -> list[int]:
    if not isinstance(value, list) or not value:
        raise PreparationError("Select at least one column for this transformation.")
    positions: list[int] = []
    for item in value:
        try:
            position = int(item)
        except (TypeError, ValueError) as exc:
            raise PreparationError("Column identifiers must be integer positions.") from exc
        if position <= 0:
            raise PreparationError("Column positions must be positive integers.")
        if position in positions:
            raise PreparationError("A transformation cannot list the same column twice.")
        positions.append(position)
    return positions


def _positive_int(value: object, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise PreparationError(f"{label} must be an integer.") from exc
    if parsed <= 0:
        raise PreparationError(f"{label} must be positive.")
    return parsed


def _positive_float(value: object, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise PreparationError(f"{label} must be numeric.") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise PreparationError(f"{label} must be a positive finite number.")
    return parsed


def normalise_step(step: dict) -> dict:
    """Return a JSON-safe transformation step with a controlled operation identifier."""
    if not isinstance(step, dict):
        raise PreparationError("Each preparation step must be an object.")
    operation = str(step.get("operation", "")).strip()
    if operation not in OPERATION_LABELS:
        raise PreparationError("Unknown preparation operation.")
    parameters = step.get("parameters", {})
    if not isinstance(parameters, dict):
        raise PreparationError("Transformation parameters must be an object.")
    try:
        serialised = json.dumps(parameters, sort_keys=True, separators=(",", ":"), allow_nan=False)
        clean_parameters = json.loads(serialised)
    except (TypeError, ValueError) as exc:
        raise PreparationError("Transformation parameters must be finite JSON values.") from exc
    return {"operation": operation, "parameters": clean_parameters}


def _referenced_columns(step: dict) -> list[int]:
    operation = step["operation"]
    parameters = step["parameters"]
    if operation in {"time_crop", "sort_time"}:
        return [_positive_int(parameters.get("time_column"), "Time column")]
    if operation == "missing_values":
        positions = _column_positions(parameters.get("columns"))
        if parameters.get("action") == "interpolate_linear":
            positions.append(_positive_int(parameters.get("coordinate_column"), "Coordinate column"))
        return positions
    if operation == "resample":
        return [
            _positive_int(parameters.get("time_column"), "Time column"),
            *_column_positions(parameters.get("columns")),
        ]
    if operation == "moving_average":
        return _column_positions(parameters.get("columns"))
    if operation == "unit_conversion":
        return [_positive_int(parameters.get("column"), "Column")]
    if operation == "select_columns":
        return _column_positions(parameters.get("columns"))
    return []


def _validate_step_shape(step: dict) -> None:
    operation = step["operation"]
    parameters = step["parameters"]
    _referenced_columns(step)
    if operation == "time_crop":
        if parameters.get("start") in {None, ""} or parameters.get("end") in {None, ""}:
            raise PreparationError("Time crop requires explicit start and end values.")
    elif operation == "row_range":
        start = _positive_int(parameters.get("start_row"), "Start row")
        end = _positive_int(parameters.get("end_row"), "End row")
        if end < start:
            raise PreparationError("End row must be greater than or equal to start row.")
    elif operation == "exclude_rows":
        rows = parameters.get("rows")
        if not isinstance(rows, list) or not rows:
            raise PreparationError("Select at least one row to exclude.")
        parsed = [_positive_int(row, "Excluded row") for row in rows]
        if len(set(parsed)) != len(parsed):
            raise PreparationError("Excluded row numbers must be unique.")
    elif operation == "missing_values":
        if parameters.get("action") not in {"remove_rows", "interpolate_linear"}:
            raise PreparationError("Missing-value action must be remove_rows or interpolate_linear.")
    elif operation == "resample":
        _positive_float(parameters.get("target_dt"), "Target dt")
    elif operation == "moving_average":
        window = _positive_int(parameters.get("window_samples"), "Window size")
        if window < 3 or window % 2 == 0:
            raise PreparationError("Moving-average window must be an odd integer of at least 3 samples.")
    elif operation == "unit_conversion" and not str(parameters.get("target_unit", "")).strip():
        raise PreparationError("Unit conversion requires a target unit.")


def validate_recipe_metadata(recipe: list[dict], columns: list[dict]) -> list[dict]:
    """Validate recipe structure and stable column references without transforming data."""
    if not isinstance(recipe, list):
        raise PreparationError("Preparation recipe must be an ordered list.")
    available = {int(column["source_position"]) for column in columns}
    clean_recipe: list[dict] = []
    for index, raw_step in enumerate(recipe, 1):
        step = normalise_step(raw_step)
        try:
            _validate_step_shape(step)
            references = _referenced_columns(step)
        except PreparationError as exc:
            raise PreparationError(f"Step {index}: {exc}") from exc
        missing = [position for position in references if position not in available]
        if missing:
            raise PreparationError(
                f"Step {index}: referenced column {missing[0]} is not available at that point."
            )
        if step["operation"] == "select_columns":
            selected = set(_column_positions(step["parameters"].get("columns")))
            available &= selected
            if not available:
                raise PreparationError(f"Step {index}: column selection cannot remove every column.")
        clean_recipe.append(step)
    return clean_recipe


def recipe_fingerprint(source_sha256: str, recipe: list[dict]) -> str:
    canonical = json.dumps(recipe, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload = f"{source_sha256}\n{ENGINE_ID}\n{ENGINE_VERSION}\n{canonical}".encode()
    return hashlib.sha256(payload).hexdigest()


def load_source_table(version) -> PreparedTable:
    """Load one inspected immutable source into the bounded worker representation."""
    if version.import_status != DatasetImportStatus.READY:
        raise PreparationError("Only a successfully inspected DatasetVersion can be prepared.")
    max_rows = int(settings.DATA_PREPARATION_MAX_ROWS)
    if version.row_count is not None and version.row_count > max_rows:
        raise PreparationError(
            "This dataset exceeds the configured in-memory preparation row limit for this instance."
        )
    columns = list(version.columns.order_by("position"))
    if not columns:
        raise PreparationError("The source has no inspected columns.")
    metadata = [
        {
            "position": column.position,
            "source_position": column.position,
            "source_name": column.source_name,
            "display_name": column.display_name,
            "inferred_type": column.inferred_type,
            "role": column.role,
            "unit": column.unit,
        }
        for column in columns
    ]
    importer = get_importer(version.source_format)
    try:
        with dataset_storage().open(version.source_path, "rb") as handle:
            source = importer.open_table(
                handle,
                filename=version.original_filename,
                options=dict(version.import_options or {}),
            )
            rows: list[list[object]] = []
            width = len(metadata)
            for raw_row in source.rows:
                if len(rows) >= max_rows:
                    raise PreparationError(
                        "This dataset exceeds the configured in-memory preparation row limit for this instance."
                    )
                row = list(raw_row)
                if len(row) > width:
                    raise PreparationError(
                        "The stored source width no longer matches its inspected column metadata."
                    )
                rows.append(row + [""] * (width - len(row)))
    except ImporterError as exc:
        raise PreparationError(str(exc)) from exc
    if not rows:
        raise PreparationError("The source contains no data rows.")
    return PreparedTable(
        rows=rows,
        columns=metadata,
        decimal_separator=str(version.import_options.get("decimal_separator", ".")),
    )


def _time_bound(value: object, mode: str, decimal_separator: str) -> float:
    if mode == "numeric":
        number = _parse_number(value, decimal_separator)
        if number is None or not math.isfinite(number):
            raise PreparationError("Time crop bounds must be finite numeric values.")
        return number
    parsed = _parse_datetime(value)
    if parsed is None:
        raise PreparationError("Datetime crop bounds must use ISO-8601 date/time values.")
    aware = parsed.tzinfo is not None
    if (mode == "datetime-aware") != aware:
        raise PreparationError("Datetime crop bounds must preserve the source timezone semantics.")
    return _time_value(parsed, decimal_separator)[1]


def _apply_time_crop(table: PreparedTable, parameters: dict) -> list[dict]:
    time_column = _positive_int(parameters.get("time_column"), "Time column")
    mode, scalars, _ = _time_series(table, time_column)
    start = _time_bound(parameters.get("start"), mode, table.decimal_separator)
    end = _time_bound(parameters.get("end"), mode, table.decimal_separator)
    if not start < end:
        raise PreparationError("Time crop end must be greater than start.")
    keep = (scalars >= start) & (scalars <= end)
    kept = int(np.count_nonzero(keep))
    if kept == 0:
        raise PreparationError("The requested time range does not overlap the data.")
    before = len(table.rows)
    table.rows = [row for row, include in zip(table.rows, keep, strict=True) if bool(include)]
    return [{"code": "TIME_CROP", "details": {"rows_before": before, "rows_after": kept}}]


def _apply_row_range(table: PreparedTable, parameters: dict) -> list[dict]:
    start = _positive_int(parameters.get("start_row"), "Start row")
    end = _positive_int(parameters.get("end_row"), "End row")
    if end < start:
        raise PreparationError("End row must be greater than or equal to start row.")
    if start > len(table.rows) or end > len(table.rows):
        raise PreparationError("Requested row range lies outside the current prepared table.")
    before = len(table.rows)
    table.rows = table.rows[start - 1 : end]
    return [
        {
            "code": "ROW_RANGE",
            "details": {"start_row": start, "end_row": end, "rows_before": before, "rows_after": len(table.rows)},
        }
    ]


def _apply_exclude_rows(table: PreparedTable, parameters: dict) -> list[dict]:
    raw_rows = parameters.get("rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise PreparationError("Select at least one row to exclude.")
    excluded = {_positive_int(item, "Excluded row") for item in raw_rows}
    if max(excluded) > len(table.rows):
        raise PreparationError("An excluded row number lies outside the current prepared table.")
    before = len(table.rows)
    table.rows = [row for index, row in enumerate(table.rows, 1) if index not in excluded]
    if not table.rows:
        raise PreparationError("Explicit row exclusion cannot remove every row.")
    return [
        {
            "code": "ROWS_EXCLUDED",
            "details": {"excluded_rows": sorted(excluded), "rows_before": before, "rows_after": len(table.rows)},
        }
    ]


def _apply_missing_values(table: PreparedTable, parameters: dict) -> list[dict]:
    columns = _column_positions(parameters.get("columns"))
    action = parameters.get("action")
    indices = [table.column_index(position) for position in columns]
    if action == "remove_rows":
        before = len(table.rows)
        table.rows = [
            row for row in table.rows if not any(_is_missing(row[index]) for index in indices)
        ]
        if not table.rows:
            raise PreparationError("Missing-value row removal would remove every row.")
        return [
            {
                "code": "MISSING_ROWS_REMOVED",
                "details": {"rows_before": before, "rows_after": len(table.rows), "columns": columns},
            }
        ]
    if action != "interpolate_linear":
        raise PreparationError("Unknown missing-value treatment.")
    coordinate = _positive_int(parameters.get("coordinate_column"), "Coordinate column")
    _, x, _ = _time_series(table, coordinate)
    if not _strictly_increasing(x):
        raise PreparationError(
            "Linear interpolation requires a strictly increasing coordinate without duplicates."
        )
    warnings: list[dict] = []
    for position in columns:
        y = _numeric_vector(table, position)
        if np.isinf(y).any():
            raise PreparationError(
                f"Column {position} contains infinite values; resolve them explicitly before interpolation."
            )
        missing = np.isnan(y)
        known = ~missing
        if int(np.count_nonzero(known)) < 2:
            raise PreparationError(
                f"Column {position} needs at least two finite known values for linear interpolation."
            )
        lower = float(np.min(x[known]))
        upper = float(np.max(x[known]))
        fillable = missing & (x > lower) & (x < upper)
        if np.any(fillable):
            y[fillable] = np.interp(x[fillable], x[known], y[known])
            target_index = table.column_index(position)
            for row_index in np.where(fillable)[0]:
                table.rows[int(row_index)][target_index] = float(y[int(row_index)])
        remaining = int(np.count_nonzero(np.isnan(y)))
        warnings.append(
            {
                "code": "LINEAR_INTERPOLATION",
                "details": {
                    "column": position,
                    "filled": int(np.count_nonzero(fillable)),
                    "remaining_missing": remaining,
                    "boundary_behavior": "no_extrapolation",
                    "coordinate_column": coordinate,
                },
            }
        )
    return warnings


def _apply_resample(table: PreparedTable, parameters: dict) -> list[dict]:
    time_column = _positive_int(parameters.get("time_column"), "Time column")
    columns = _column_positions(parameters.get("columns"))
    available_non_time = {
        int(column["source_position"])
        for column in table.columns
        if int(column["source_position"]) != time_column
    }
    if set(columns) != available_non_time:
        raise PreparationError(
            "Resampling must explicitly include every remaining non-time column; add a column-selection step first if needed."
        )
    mode, x, datetimes = _time_series(table, time_column)
    if len(x) < 2 or not _strictly_increasing(x):
        raise PreparationError("Resampling requires a strictly increasing time axis without duplicates.")
    dt = _positive_float(parameters.get("target_dt"), "Target dt")
    time_meta = table.column(time_column)
    declared_dt_unit = str(parameters.get("dt_unit", "")).strip()
    source_unit = str(time_meta.get("unit", "")).strip()
    if mode == "numeric" and declared_dt_unit and source_unit and declared_dt_unit != source_unit:
        raise PreparationError(
            "Target dt must use the current time-column unit; convert the time unit explicitly first."
        )
    if mode.startswith("datetime") and declared_dt_unit.lower() not in {"", "s", "sec", "second", "seconds"}:
        raise PreparationError("Datetime resampling target dt is expressed in seconds.")
    span = float(x[-1] - x[0])
    count = math.floor(span / dt + 1e-12) + 1
    if count < 2:
        raise PreparationError("Target dt is too large to produce at least two samples.")
    grid = x[0] + np.arange(count, dtype=float) * dt
    numeric_columns: dict[int, np.ndarray] = {}
    for position in columns:
        values = _numeric_vector(table, position)
        if not np.isfinite(values).all():
            raise PreparationError(
                f"Column {position} contains missing or non-finite values; treat them explicitly before resampling."
            )
        numeric_columns[position] = np.interp(grid, x, values)
    time_index = table.column_index(time_column)
    column_indices = {position: table.column_index(position) for position in columns}
    first_datetime = datetimes[0]
    new_rows: list[list[object]] = []
    for output_index, scalar in enumerate(grid):
        row = ["" for _ in table.columns]
        if mode == "numeric":
            row[time_index] = float(scalar)
        else:
            assert first_datetime is not None
            row[time_index] = first_datetime + timedelta(seconds=float(scalar - grid[0]))
        for position, values in numeric_columns.items():
            row[column_indices[position]] = float(values[output_index])
        new_rows.append(row)
    before = len(table.rows)
    table.rows = new_rows
    return [
        {
            "code": "RESAMPLED",
            "details": {
                "rows_before": before,
                "rows_after": len(new_rows),
                "target_dt": dt,
                "dt_unit": declared_dt_unit or ("s" if mode.startswith("datetime") else source_unit),
                "method": "linear",
                "grid": "uniform",
            },
        }
    ]


def _apply_moving_average(table: PreparedTable, parameters: dict) -> list[dict]:
    columns = _column_positions(parameters.get("columns"))
    window = _positive_int(parameters.get("window_samples"), "Window size")
    if window < 3 or window % 2 == 0:
        raise PreparationError("Moving-average window must be an odd integer of at least 3 samples.")
    if window > len(table.rows):
        raise PreparationError("Moving-average window cannot exceed the number of rows.")
    half = window // 2
    for position in columns:
        values = _numeric_vector(table, position)
        if not np.isfinite(values).all():
            raise PreparationError(
                f"Column {position} contains missing or non-finite values; treat them explicitly before smoothing."
            )
        averaged = np.convolve(values, np.ones(window, dtype=float) / window, mode="valid")
        target_index = table.column_index(position)
        for offset, value in enumerate(averaged, half):
            table.rows[offset][target_index] = float(value)
    return [
        {
            "code": "MOVING_AVERAGE",
            "details": {
                "columns": columns,
                "window_samples": window,
                "boundary_behavior": "preserve_original_edges",
            },
        }
    ]


def _apply_unit_conversion(table: PreparedTable, parameters: dict) -> list[dict]:
    position = _positive_int(parameters.get("column"), "Column")
    target_unit = str(parameters.get("target_unit", "")).strip()
    if not target_unit:
        raise PreparationError("Unit conversion requires a target unit.")
    metadata = table.column(position)
    source_unit = str(metadata.get("unit", "")).strip()
    if not source_unit:
        raise PreparationError("The selected column has no declared source unit to convert from.")
    values = _numeric_vector(table, position)
    if np.isinf(values).any():
        raise PreparationError("Unit conversion does not replace infinite values.")
    try:
        converted = _UREG.Quantity(values, source_unit).to(target_unit).magnitude
    except (DimensionalityError, UndefinedUnitError, ValueError) as exc:
        raise PreparationError(
            f"Units {source_unit!r} and {target_unit!r} are not a supported compatible conversion."
        ) from exc
    target_index = table.column_index(position)
    for row_index, value in enumerate(np.asarray(converted, dtype=float)):
        if math.isnan(float(value)):
            continue
        table.rows[row_index][target_index] = float(value)
    metadata["unit"] = target_unit
    return [
        {
            "code": "UNIT_CONVERTED",
            "details": {
                "column": position,
                "source_unit": source_unit,
                "target_unit": target_unit,
                "engine": "Pint",
            },
        }
    ]


def _apply_select_columns(table: PreparedTable, parameters: dict) -> list[dict]:
    selected = set(_column_positions(parameters.get("columns")))
    indices = [
        index
        for index, column in enumerate(table.columns)
        if int(column["source_position"]) in selected
    ]
    if not indices:
        raise PreparationError("Column selection cannot remove every column.")
    before = len(table.columns)
    table.columns = [table.columns[index] for index in indices]
    table.rows = [[row[index] for index in indices] for row in table.rows]
    table.reindex()
    return [
        {
            "code": "COLUMNS_SELECTED",
            "details": {
                "source_positions": [int(column["source_position"]) for column in table.columns],
                "columns_before": before,
                "columns_after": len(table.columns),
            },
        }
    ]


def _apply_sort_time(table: PreparedTable, parameters: dict) -> list[dict]:
    time_column = _positive_int(parameters.get("time_column"), "Time column")
    _, scalars, _ = _time_series(table, time_column)
    order = np.argsort(scalars, kind="stable")
    table.rows = [table.rows[int(index)] for index in order]
    return [
        {
            "code": "TIME_SORTED",
            "details": {"time_column": time_column, "direction": "ascending", "stable": True},
        }
    ]


_EXECUTORS = {
    "time_crop": _apply_time_crop,
    "row_range": _apply_row_range,
    "exclude_rows": _apply_exclude_rows,
    "missing_values": _apply_missing_values,
    "resample": _apply_resample,
    "moving_average": _apply_moving_average,
    "unit_conversion": _apply_unit_conversion,
    "select_columns": _apply_select_columns,
    "sort_time": _apply_sort_time,
}


def apply_recipe(table: PreparedTable, recipe: list[dict]) -> tuple[PreparedTable, list[dict]]:
    """Apply the ordered recipe exactly once in the order supplied by the user."""
    clean_recipe = validate_recipe_metadata(recipe, table.metadata_snapshot())
    warnings: list[dict] = []
    for step_index, step in enumerate(clean_recipe, 1):
        step_warnings = _EXECUTORS[step["operation"]](table, step["parameters"])
        warnings.extend({**warning, "step": step_index} for warning in step_warnings)
    if not table.rows:
        raise PreparationError("The preparation produced no data rows.")
    return table, warnings


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    return value


def csv_chunks(table: PreparedTable):
    """Yield deterministic UTF-8 CSV bytes without altering scientific cell content."""
    headers = [
        str(column.get("display_name") or f"Column {index}")
        for index, column in enumerate(table.columns, 1)
    ]
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=",", lineterminator="\n")
    writer.writerow(headers)
    yield buffer.getvalue().encode("utf-8")
    buffer.seek(0)
    buffer.truncate(0)
    for row in table.rows:
        writer.writerow([_csv_value(value) for value in row])
        yield buffer.getvalue().encode("utf-8")
        buffer.seek(0)
        buffer.truncate(0)


def inspect_prepared_table(table: PreparedTable) -> tuple[dict, list[dict]]:
    """Run the same data-quality inspection contract on the materialized prepared values."""
    metadata = table.metadata_snapshot()
    annotations = {
        int(column["position"]): {
            "role": column.get("role", "OTHER"),
            "unit": column.get("unit", ""),
        }
        for column in metadata
    }
    source = TabularSource(
        headers=[str(column.get("display_name", "")) for column in metadata],
        source_headers=[str(column.get("source_name", "")) for column in metadata],
        rows=iter([list(row) for row in table.rows]),
        detected_options={},
        metadata={
            "used_options": {
                "encoding": "utf-8",
                "delimiter": ",",
                "has_header": True,
                "decimal_separator": ".",
            },
            "source_has_header": True,
        },
    )
    result = inspect_table(source, annotations=annotations)
    inferred_by_position = {int(column["position"]): column for column in result["columns"]}
    for column in metadata:
        inspected = inferred_by_position[int(column["position"])]
        column.update(
            {
                "inferred_type": inspected["inferred_type"],
                "missing_count": inspected["missing_count"],
                "non_numeric_count": inspected["non_numeric_count"],
                "non_finite_count": inspected["non_finite_count"],
                "summary": inspected["summary"],
            }
        )
    return result, metadata
