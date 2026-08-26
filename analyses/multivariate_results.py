"""Lossless private serialization for public AgencityLab multivariate results.

Only values returned by ``agencitylab.api.compute_multivariate_agencity`` are
stored. Studio never reconstructs component or aggregate scientific quantities.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass

import numpy as np

MULTIVARIATE_RESULT_SCHEMA_VERSION = "2"
MULTIVARIATE_RESULT_FORMAT = "ZIP_NPY_JSON"

AGGREGATE_ARRAY_KEYS = (
    "xi",
    "A_ref",
    "tau",
    "w",
    "P_c_components",
    "P_c_total",
    "beta_components",
    "b_components",
    "beta_multi",
    "beta_multi_defined",
    "b_total",
)

COMPONENT_ARRAY_KEYS = (
    "xi",
    "u",
    "u_star",
    "t_star",
    "P_c",
    "X_star",
    "A_star",
    "M",
    "O",
    "D",
    "S",
    "J",
    "U",
    "theta",
    "beta",
    "b",
)


class MultivariateResultArtifactError(ValueError):
    """Stored multivariate result is missing, corrupt, or incompatible."""


@dataclass(frozen=True)
class SerializedMultivariateResult:
    data: bytes
    sha256: str
    size_bytes: int
    manifest: dict


def _json_safe(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _array_descriptor(name: str, array: np.ndarray, member: str) -> dict:
    return {
        "name": name,
        "shape": list(array.shape),
        "dtype": str(array.dtype),
        "member": member,
    }


def _write_array(archive: zipfile.ZipFile, member: str, array: np.ndarray) -> None:
    payload = io.BytesIO()
    np.lib.format.write_array(payload, np.asarray(array), allow_pickle=False)
    info = zipfile.ZipInfo(member, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, payload.getvalue())


def serialize_multivariate_result(*, result: dict, run) -> SerializedMultivariateResult:
    """Serialize exact public Lab outputs without downcasting or scientific derivation."""
    components = list(run.components.select_related("observable_definition").order_by("position"))
    lab_components = list(result.get("components") or [])
    if int(result.get("n_components", -1)) != len(components) or len(lab_components) != len(components):
        raise MultivariateResultArtifactError(
            "AgencityLab component count does not match the immutable Run contract."
        )

    aggregate_arrays: dict[str, np.ndarray] = {}
    aggregate_inventory: list[dict] = []
    for key in AGGREGATE_ARRAY_KEYS:
        if key not in result:
            continue
        array = np.asarray(result[key])
        member = f"aggregate/{key}.npy"
        aggregate_arrays[key] = array
        aggregate_inventory.append(_array_descriptor(key, array, member))

    component_arrays: list[dict[str, np.ndarray]] = []
    component_manifest: list[dict] = []
    for index, (snapshot, public_component) in enumerate(
        zip(components, lab_components, strict=True),
        start=1,
    ):
        arrays: dict[str, np.ndarray] = {}
        inventory: list[dict] = []
        for key in COMPONENT_ARRAY_KEYS:
            if key not in public_component:
                continue
            array = np.asarray(public_component[key])
            member = f"components/{index}/{key}.npy"
            arrays[key] = array
            inventory.append(_array_descriptor(key, array, member))
        component_arrays.append(arrays)
        component_manifest.append(
            {
                "position": snapshot.position,
                "observable_definition_id": str(snapshot.observable_definition_id),
                "observable_name": snapshot.observable_definition.name,
                "observable_symbol": snapshot.observable_definition.symbol,
                "source_column_identity": snapshot.source_column_identity,
                "source_column_position": snapshot.source_column_position,
                "source_name": snapshot.source_name,
                "display_name": snapshot.display_name,
                "unit": snapshot.unit,
                "parameter_snapshot": _json_safe(snapshot.parameter_snapshot),
                "series": inventory,
                "lab_context": {
                    "A_ref": _json_safe(public_component.get("A_ref")),
                    "tau": _json_safe(public_component.get("tau")),
                    "w": _json_safe(public_component.get("w")),
                    "window_mode": _json_safe(public_component.get("window_mode")),
                },
            }
        )

    manifest = {
        "schema_version": MULTIVARIATE_RESULT_SCHEMA_VERSION,
        "format": MULTIVARIATE_RESULT_FORMAT,
        "analysis_kind": "MULTIVARIATE",
        "run_id": str(run.pk),
        "analysis_id": str(run.analysis_id),
        "source_sha256": run.source_sha256,
        "system_revision_id": str(run.system_revision_id),
        "system_configuration_fingerprint": run.system_configuration_fingerprint,
        "execution_fingerprint": run.execution_fingerprint,
        "agencitylab_version": run.agencitylab_version,
        "studio_version": run.studio_version,
        "n_components": int(result.get("n_components", len(components))),
        "aggregate_series": aggregate_inventory,
        "components": component_manifest,
        "aggregation": _json_safe(result.get("aggregation")),
        "scientific_boundary": _json_safe(result.get("scientific_boundary")),
        "public_function": (run.analysis_options or {}).get("public_function"),
        "scientific_status": (run.analysis_options or {}).get("scientific_status"),
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        info = zipfile.ZipInfo("manifest.json", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(
            info,
            json.dumps(
                manifest,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8"),
        )
        for key, array in aggregate_arrays.items():
            _write_array(archive, f"aggregate/{key}.npy", array)
        for index, arrays in enumerate(component_arrays, start=1):
            for key, array in arrays.items():
                _write_array(archive, f"components/{index}/{key}.npy", array)

    data = buffer.getvalue()
    return SerializedMultivariateResult(
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        manifest=manifest,
    )
