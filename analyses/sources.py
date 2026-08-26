"""Common schema and exact-column readers for raw and prepared Analysis sources."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass

import numpy as np
from django.conf import settings

from datasets.importers import get_importer
from datasets.importers.base import ImporterError
from datasets.models import DataPreparationStatus, DatasetImportStatus
from datasets.storage import dataset_storage

from .models import SourceType


class SourceContractError(ValueError):
    """User-facing source incompatibility that must not trigger hidden preparation."""


@dataclass(frozen=True)
class SourceDescriptor:
    source_type: str
    source_id: str
    sha256: str
    rows: int | None
    columns: int | None
    column_metadata: tuple[dict, ...]
    quality_issues: tuple[dict, ...]
    lineage: dict


def describe_raw(version) -> SourceDescriptor:
    if version.import_status != DatasetImportStatus.READY:
        raise SourceContractError("Only a READY DatasetVersion can be analysed.")
    columns = tuple(
        {
            "identity": str(column.pk),
            "position": column.position,
            "source_position": column.position,
            "source_name": column.source_name,
            "display_name": column.display_name,
            "unit": column.unit,
            "role": column.role,
            "inferred_type": column.inferred_type,
            "missing_count": column.missing_count,
            "non_numeric_count": column.non_numeric_count,
            "non_finite_count": column.non_finite_count,
        }
        for column in version.columns.order_by("position")
    )
    return SourceDescriptor(
        source_type=SourceType.RAW_DATASET_VERSION,
        source_id=str(version.pk),
        sha256=version.source_sha256,
        rows=version.row_count,
        columns=version.column_count,
        column_metadata=columns,
        quality_issues=tuple(version.quality_issues or []),
        lineage={"dataset_id": str(version.dataset_id), "version_number": version.version_number},
    )


def describe_prepared(artifact) -> SourceDescriptor:
    if artifact.preparation.status != DataPreparationStatus.READY:
        raise SourceContractError("Only READY prepared data can be analysed.")
    columns = []
    for item in artifact.column_metadata or []:
        position = int(item["position"])
        columns.append(
            {
                "identity": f"{artifact.pk}:{position}",
                "position": position,
                "source_position": int(item.get("source_position", position)),
                "source_name": item.get("source_name", ""),
                "display_name": item.get("display_name", ""),
                "unit": item.get("unit", ""),
                "role": item.get("role", "OTHER"),
                "inferred_type": item.get("inferred_type", ""),
                "missing_count": int(item.get("missing_count", 0)),
                "non_numeric_count": int(item.get("non_numeric_count", 0)),
                "non_finite_count": int(item.get("non_finite_count", 0)),
            }
        )
    preparation = artifact.preparation
    return SourceDescriptor(
        source_type=SourceType.PREPARED_DATA,
        source_id=str(artifact.pk),
        sha256=artifact.prepared_sha256,
        rows=artifact.row_count,
        columns=artifact.column_count,
        column_metadata=tuple(columns),
        quality_issues=tuple(artifact.quality_issues or []),
        lineage={
            "preparation_id": str(preparation.pk),
            "recipe_hash": preparation.recipe_hash,
            "source_dataset_version_id": str(preparation.source_version_id),
            "source_sha256": preparation.source_version.source_sha256,
        },
    )


def descriptor_for(*, dataset_version=None, prepared_artifact=None) -> SourceDescriptor:
    if (dataset_version is None) == (prepared_artifact is None):
        raise SourceContractError("Exactly one analysis source must be selected.")
    return describe_raw(dataset_version) if dataset_version is not None else describe_prepared(prepared_artifact)


def column_at(descriptor: SourceDescriptor, position: int) -> dict:
    for column in descriptor.column_metadata:
        if int(column["position"]) == int(position):
            return dict(column)
    raise SourceContractError(f"Column position {position} does not exist in the pinned source.")


def _number(value, decimal_separator: str = ".") -> float:
    if isinstance(value, bool) or value is None:
        raise SourceContractError("Selected analysis columns must contain only numeric values.")
    if isinstance(value, (int, float, np.integer, np.floating)):
        number = float(value)
    else:
        text = str(value).strip()
        if not text:
            raise SourceContractError("Selected analysis columns contain missing values.")
        if decimal_separator == ",":
            if "." in text:
                raise SourceContractError("A selected value conflicts with the source decimal-separator contract.")
            text = text.replace(",", ".")
        elif "," in text:
            raise SourceContractError("A selected value is not numeric under the source import contract.")
        try:
            number = float(text)
        except ValueError as exc:
            raise SourceContractError("Selected analysis columns must contain only numeric values.") from exc
    if not math.isfinite(number):
        raise SourceContractError("Selected analysis columns must contain only finite values.")
    return number


def _bounded(values: list[float]) -> None:
    maximum = int(getattr(settings, "ANALYSIS_MAX_ROWS", settings.DATA_PREPARATION_MAX_ROWS))
    if len(values) > maximum:
        raise SourceContractError("This source exceeds the configured analysis row limit for this instance.")


def _read_raw(version, coordinate_position: int, observable_position: int) -> tuple[np.ndarray, np.ndarray]:
    importer = get_importer(version.source_format)
    decimal = str((version.import_options or {}).get("decimal_separator", "."))
    xi: list[float] = []
    u: list[float] = []
    try:
        with dataset_storage().open(version.source_path, "rb") as handle:
            table = importer.open_table(handle, filename=version.original_filename, options=dict(version.import_options or {}))
            for row in table.rows:
                if len(row) < max(coordinate_position, observable_position):
                    raise SourceContractError("Stored source width no longer matches its inspected schema.")
                xi.append(_number(row[coordinate_position - 1], decimal))
                u.append(_number(row[observable_position - 1], decimal))
                _bounded(xi)
    except ImporterError as exc:
        raise SourceContractError(str(exc)) from exc
    return np.asarray(xi, dtype=float), np.asarray(u, dtype=float)


def _read_prepared(artifact, coordinate_position: int, observable_position: int) -> tuple[np.ndarray, np.ndarray]:
    xi: list[float] = []
    u: list[float] = []
    with dataset_storage().open(artifact.storage_path, "r") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            if len(row) < max(coordinate_position, observable_position):
                raise SourceContractError("Prepared artifact width no longer matches its immutable schema.")
            xi.append(_number(row[coordinate_position - 1]))
            u.append(_number(row[observable_position - 1]))
            _bounded(xi)
    return np.asarray(xi, dtype=float), np.asarray(u, dtype=float)


def materialize_vectors(*, dataset_version=None, prepared_artifact=None, coordinate_position: int, observable_position: int) -> tuple[np.ndarray, np.ndarray]:
    """Read exactly two pinned columns without sorting, filling, filtering or resampling."""
    if (dataset_version is None) == (prepared_artifact is None):
        raise SourceContractError("Exactly one analysis source must be selected.")
    if dataset_version is not None:
        return _read_raw(dataset_version, coordinate_position, observable_position)
    return _read_prepared(prepared_artifact, coordinate_position, observable_position)


def _read_raw_matrix(
    version,
    coordinate_position: int,
    component_positions: tuple[int, ...],
) -> tuple[np.ndarray, np.ndarray]:
    importer = get_importer(version.source_format)
    decimal = str((version.import_options or {}).get("decimal_separator", "."))
    xi: list[float] = []
    components: list[list[float]] = [[] for _ in component_positions]
    required_width = max((coordinate_position, *component_positions))
    try:
        with dataset_storage().open(version.source_path, "rb") as handle:
            table = importer.open_table(
                handle,
                filename=version.original_filename,
                options=dict(version.import_options or {}),
            )
            for row in table.rows:
                if len(row) < required_width:
                    raise SourceContractError(
                        "Stored source width no longer matches its inspected schema."
                    )
                xi.append(_number(row[coordinate_position - 1], decimal))
                for target, position in zip(components, component_positions, strict=True):
                    target.append(_number(row[position - 1], decimal))
                _bounded(xi)
    except ImporterError as exc:
        raise SourceContractError(str(exc)) from exc
    matrix = np.column_stack([np.asarray(values, dtype=float) for values in components])
    return np.asarray(xi, dtype=float), matrix


def _read_prepared_matrix(
    artifact,
    coordinate_position: int,
    component_positions: tuple[int, ...],
) -> tuple[np.ndarray, np.ndarray]:
    xi: list[float] = []
    components: list[list[float]] = [[] for _ in component_positions]
    required_width = max((coordinate_position, *component_positions))
    with dataset_storage().open(artifact.storage_path, "r") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            if len(row) < required_width:
                raise SourceContractError(
                    "Prepared artifact width no longer matches its immutable schema."
                )
            xi.append(_number(row[coordinate_position - 1]))
            for target, position in zip(components, component_positions, strict=True):
                target.append(_number(row[position - 1]))
            _bounded(xi)
    matrix = np.column_stack([np.asarray(values, dtype=float) for values in components])
    return np.asarray(xi, dtype=float), matrix


def materialize_matrix(
    *,
    dataset_version=None,
    prepared_artifact=None,
    coordinate_position: int,
    component_positions,
) -> tuple[np.ndarray, np.ndarray]:
    """Read one coordinate and ordered components exactly as stored.

    No sorting, joining, interpolation, resampling, normalization, row dropping,
    truncation, padding, or missing-value repair occurs here. The returned matrix
    is sample-major because that is the public AgencityLab 1.1.3 default contract.
    """
    if (dataset_version is None) == (prepared_artifact is None):
        raise SourceContractError("Exactly one analysis source must be selected.")
    positions = tuple(int(value) for value in component_positions)
    if not positions:
        raise SourceContractError("At least one multivariate component column is required.")
    if dataset_version is not None:
        return _read_raw_matrix(dataset_version, int(coordinate_position), positions)
    return _read_prepared_matrix(prepared_artifact, int(coordinate_position), positions)
