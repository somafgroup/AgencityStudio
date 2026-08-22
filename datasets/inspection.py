"""Deterministic Dataset inspection diagnostics with no scientific preprocessing."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime

from .importers.base import ImporterError, TabularSource
from .models import DatasetColumnRole, DatasetColumnType


@dataclass
class ColumnAccumulator:
    position: int
    source_name: str
    display_name: str
    missing: int = 0
    numeric: int = 0
    datetimes: int = 0
    booleans: int = 0
    text: int = 0
    nonfinite: int = 0
    minimum: float | None = None
    maximum: float | None = None
    datetime_min: datetime | None = None
    datetime_max: datetime | None = None
    time_values: list[object] = field(default_factory=list)

    @property
    def nonmissing(self) -> int:
        return self.numeric + self.datetimes + self.booleans + self.text


def _issue(code: str, severity: str, *, column_position: int | None = None, **details) -> dict:
    return {
        "code": code,
        "severity": severity,
        "column_position": column_position,
        "details": details,
    }


def _parse_number(value: object, decimal_separator: str) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if decimal_separator == ",":
        text = text.replace(".", "").replace(",", ".")
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
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _observe(acc: ColumnAccumulator, value: object, *, decimal_separator: str, keep_time: bool) -> None:
    if value is None or (isinstance(value, str) and not value.strip()):
        acc.missing += 1
        if keep_time:
            acc.time_values.append(None)
        return
    if keep_time:
        acc.time_values.append(value)
    if isinstance(value, bool):
        acc.booleans += 1
        return
    number = _parse_number(value, decimal_separator)
    if number is not None:
        acc.numeric += 1
        if not math.isfinite(number):
            acc.nonfinite += 1
            return
        acc.minimum = number if acc.minimum is None else min(acc.minimum, number)
        acc.maximum = number if acc.maximum is None else max(acc.maximum, number)
        return
    parsed_datetime = _parse_datetime(value)
    if parsed_datetime is not None:
        acc.datetimes += 1
        try:
            acc.datetime_min = (
                parsed_datetime
                if acc.datetime_min is None or parsed_datetime < acc.datetime_min
                else acc.datetime_min
            )
            acc.datetime_max = (
                parsed_datetime
                if acc.datetime_max is None or parsed_datetime > acc.datetime_max
                else acc.datetime_max
            )
        except TypeError:
            # Mixed timezone-aware/naive values remain preserved and are diagnosed later if used as time.
            pass
        return
    acc.text += 1


def _inferred_type(acc: ColumnAccumulator) -> str:
    if acc.nonmissing == 0:
        return DatasetColumnType.EMPTY
    if acc.numeric == acc.nonmissing:
        return DatasetColumnType.NUMERIC
    if acc.datetimes == acc.nonmissing:
        return DatasetColumnType.DATETIME
    if acc.booleans == acc.nonmissing:
        return DatasetColumnType.BOOLEAN
    if sum(value > 0 for value in (acc.numeric, acc.datetimes, acc.booleans, acc.text)) > 1:
        return DatasetColumnType.MIXED
    return DatasetColumnType.TEXT


def _time_scalar(value: object, *, decimal_separator: str) -> tuple[str, float] | None:
    number = _parse_number(value, decimal_separator)
    if number is not None and math.isfinite(number):
        return "numeric", number
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is not None:
        return "datetime-aware", parsed.timestamp()
    seconds = (
        parsed.toordinal() * 86400
        + parsed.hour * 3600
        + parsed.minute * 60
        + parsed.second
        + parsed.microsecond / 1_000_000
    )
    return "datetime-naive", seconds


def _time_quality(
    acc: ColumnAccumulator,
    *,
    decimal_separator: str,
    unit: str,
) -> tuple[list[dict], dict]:
    issues: list[dict] = []
    scalars: list[float] = []
    modes: set[str] = set()
    unreadable = 0
    seen: set[float] = set()
    duplicate_count = 0
    for raw in acc.time_values:
        if raw is None:
            unreadable += 1
            continue
        parsed = _time_scalar(raw, decimal_separator=decimal_separator)
        if parsed is None:
            unreadable += 1
            continue
        mode, scalar = parsed
        modes.add(mode)
        if scalar in seen:
            duplicate_count += 1
        seen.add(scalar)
        scalars.append(scalar)
    if unreadable:
        issues.append(
            _issue(
                "TIME_UNREADABLE",
                "ERROR",
                column_position=acc.position,
                count=unreadable,
            )
        )
    if len(modes) > 1:
        issues.append(
            _issue(
                "TIME_MIXED_REPRESENTATION",
                "ERROR",
                column_position=acc.position,
                representations=sorted(modes),
            )
        )
    if duplicate_count:
        issues.append(
            _issue(
                "TIME_DUPLICATE",
                "WARNING",
                column_position=acc.position,
                count=duplicate_count,
            )
        )
    summary: dict = {
        "sample_count": len(acc.time_values),
        "finite_time_count": len(scalars),
        "strictly_increasing": None,
        "sampling_regular": None,
    }
    if len(scalars) >= 2 and len(modes) <= 1:
        diffs = [right - left for left, right in zip(scalars, scalars[1:], strict=False)]
        strictly_increasing = all(delta > 0 for delta in diffs)
        summary["strictly_increasing"] = strictly_increasing
        if not strictly_increasing:
            issues.append(
                _issue("TIME_NON_MONOTONIC", "WARNING", column_position=acc.position)
            )
        positive_diffs = [delta for delta in diffs if delta > 0 and math.isfinite(delta)]
        if positive_diffs:
            median_dt = statistics.median(positive_diffs)
            min_dt = min(positive_diffs)
            max_dt = max(positive_diffs)
            tolerance = max(1e-12, abs(median_dt) * 1e-12)
            regular = all(
                math.isclose(delta, median_dt, rel_tol=1e-6, abs_tol=tolerance)
                for delta in positive_diffs
            )
            summary.update(
                {
                    "start": scalars[0],
                    "end": scalars[-1],
                    "duration": scalars[-1] - scalars[0],
                    "minimum_dt": min_dt,
                    "median_dt": median_dt,
                    "maximum_dt": max_dt,
                    "sampling_regular": regular,
                    "regularity_rel_tol": 1e-6,
                }
            )
            mode = next(iter(modes), "")
            if mode.startswith("datetime") or unit.strip().lower() in {
                "s",
                "sec",
                "second",
                "seconds",
            }:
                if median_dt > 0:
                    summary["observed_sampling_frequency_hz"] = 1.0 / median_dt
            if not regular:
                issues.append(
                    _issue(
                        "IRREGULAR_SAMPLING",
                        "WARNING",
                        column_position=acc.position,
                        minimum_dt=min_dt,
                        median_dt=median_dt,
                        maximum_dt=max_dt,
                        numerical_rel_tol=1e-6,
                    )
                )
            if median_dt > 0 and max_dt > median_dt * 1.5:
                issues.append(
                    _issue(
                        "POTENTIAL_SAMPLING_GAP",
                        "INFO",
                        column_position=acc.position,
                        maximum_dt=max_dt,
                        median_dt=median_dt,
                        heuristic_multiplier=1.5,
                    )
                )
    return issues, summary


def inspect_table(
    table: TabularSource,
    *,
    annotations: dict[int, dict] | None = None,
) -> dict:
    """Inspect raw values without sorting, filling, filtering, resampling or other mutation."""
    annotations = annotations or {}
    used_options = dict(table.metadata.get("used_options", {}))
    decimal_separator = used_options.get("decimal_separator", ".")
    accumulators = [
        ColumnAccumulator(position=index, source_name=source, display_name=display)
        for index, (source, display) in enumerate(
            zip(table.source_headers, table.headers, strict=False), 1
        )
    ]
    issues: list[dict] = []
    source_names = [name for name in table.source_headers if name]
    duplicate_headers = sorted({name for name in source_names if source_names.count(name) > 1})
    if duplicate_headers:
        issues.append(_issue("DUPLICATE_HEADER", "WARNING", names=duplicate_headers))
    row_count = 0
    width_mismatch = 0
    for row in table.rows:
        row_count += 1
        if len(row) != len(accumulators):
            width_mismatch += 1
        while len(accumulators) < len(row):
            position = len(accumulators) + 1
            accumulators.append(
                ColumnAccumulator(position=position, source_name="", display_name=f"Column {position}")
            )
        padded = list(row) + [""] * max(0, len(accumulators) - len(row))
        for acc, value in zip(accumulators, padded, strict=False):
            annotation = annotations.get(acc.position, {})
            _observe(
                acc,
                value,
                decimal_separator=decimal_separator,
                keep_time=annotation.get("role") == DatasetColumnRole.TIME,
            )
    if row_count == 0:
        raise ImporterError("The source contains no data rows.")
    if width_mismatch:
        issues.append(_issue("ROW_WIDTH_MISMATCH", "WARNING", count=width_mismatch))
    formula_count = int(table.metadata.get("formula_cell_count", 0))
    if formula_count:
        issues.append(_issue("FORMULA_CELLS", "WARNING", count=formula_count))

    columns: list[dict] = []
    time_summary: dict = {}
    for acc in accumulators:
        inferred = _inferred_type(acc)
        annotation = annotations.get(acc.position, {})
        role = annotation.get("role", DatasetColumnRole.OTHER)
        unit = str(annotation.get("unit", "")).strip()
        if acc.missing:
            issues.append(
                _issue(
                    "MISSING_VALUES",
                    "WARNING",
                    column_position=acc.position,
                    count=acc.missing,
                )
            )
        if acc.nonfinite:
            issues.append(
                _issue(
                    "INFINITE_VALUES",
                    "WARNING",
                    column_position=acc.position,
                    count=acc.nonfinite,
                )
            )
        non_numeric = acc.nonmissing - acc.numeric
        if role == DatasetColumnRole.OBSERVABLE and non_numeric:
            issues.append(
                _issue(
                    "NON_NUMERIC_VALUES",
                    "WARNING",
                    column_position=acc.position,
                    count=non_numeric,
                )
            )
        summary: dict = {}
        if acc.minimum is not None:
            summary["minimum"] = acc.minimum
            summary["maximum"] = acc.maximum
        if acc.datetime_min is not None:
            summary["minimum_datetime"] = acc.datetime_min.isoformat()
            summary["maximum_datetime"] = acc.datetime_max.isoformat() if acc.datetime_max else None
        columns.append(
            {
                "position": acc.position,
                "source_name": acc.source_name,
                "display_name": acc.display_name,
                "inferred_type": inferred,
                "role": role,
                "unit": unit,
                "missing_count": acc.missing,
                "non_numeric_count": non_numeric,
                "non_finite_count": acc.nonfinite,
                "summary": summary,
            }
        )
        if role == DatasetColumnRole.TIME:
            time_issues, time_summary = _time_quality(
                acc,
                decimal_separator=decimal_separator,
                unit=unit,
            )
            issues.extend(time_issues)

    severity_counts = {
        severity: sum(1 for issue in issues if issue["severity"] == severity)
        for severity in ("INFO", "WARNING", "ERROR")
    }
    return {
        "row_count": row_count,
        "column_count": len(accumulators),
        "columns": columns,
        "issues": issues,
        "summary": {
            "source_has_header": bool(table.metadata.get("source_has_header", True)),
            "quality_counts": severity_counts,
            "time": time_summary,
        },
        "detected_options": dict(table.detected_options),
        "used_options": used_options,
    }
