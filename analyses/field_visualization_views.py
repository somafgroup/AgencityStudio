"""Private visualization endpoints for immutable observable spatial field results."""

from __future__ import annotations

import math

import numpy as np
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _

from .field_contract import FIELD_ANALYSIS_KIND
from .field_results import FieldResultArtifactError
from .field_storage import open_observable_field_result_reader
from .models import RunStatus
from .views import _analysis_context, _run_or_404

FIELD_SECTIONS = (
    ("overview", _("Overview")),
    ("observable", _("Field Observable")),
    ("state", _("Agencity State Field")),
    ("flux", _("Agencity Flux Field")),
    ("local", _("Local Trace")),
    ("reproducibility", _("Reproducibility")),
)


def _field_run(user, analysis_id, run_id):
    analysis, run = _run_or_404(user, analysis_id, run_id)
    if analysis.analysis_kind != FIELD_ANALYSIS_KIND:
        raise Http404
    return analysis, run


def _int_list(value: str) -> tuple[int, ...]:
    if not str(value or "").strip():
        return tuple()
    try:
        return tuple(int(item.strip()) for item in str(value).split(",") if item.strip())
    except ValueError as exc:
        raise FieldResultArtifactError("Spatial indices must be comma-separated integers.") from exc


def _fixed(value: str) -> dict[int, int]:
    fixed: dict[int, int] = {}
    if not str(value or "").strip():
        return fixed
    try:
        for item in str(value).split(","):
            dimension, index = item.split(":", 1)
            fixed[int(dimension.strip())] = int(index.strip())
    except ValueError as exc:
        raise FieldResultArtifactError("Fixed dimensions must use dimension:index pairs.") from exc
    return fixed


def _complex_value(value):
    scalar = np.asarray(value).item()
    if isinstance(scalar, complex):
        return {
            "real": float(scalar.real),
            "imag": float(scalar.imag),
            "magnitude": float(abs(scalar)),
            "phase": float(np.angle(scalar)),
        }
    if isinstance(scalar, (bool, np.bool_)):
        return bool(scalar)
    return float(scalar)


def _representation(array: np.ndarray, mode: str) -> np.ndarray:
    data = np.asarray(array)
    if np.iscomplexobj(data):
        if mode == "real":
            return np.real(data)
        if mode == "imag":
            return np.imag(data)
        if mode == "phase":
            return np.angle(data)
        if mode == "magnitude":
            return np.abs(data)
        raise FieldResultArtifactError("Unknown complex display representation.")
    if mode not in {"value", "magnitude", "real"}:
        raise FieldResultArtifactError("This display representation requires a complex field.")
    return np.asarray(data, dtype=float)


def _sample_indices(length: int, maximum: int) -> np.ndarray:
    if length <= maximum:
        return np.arange(length, dtype=int)
    return np.unique(np.linspace(0, length - 1, maximum, dtype=int))


def _display_grid_indices(shape: tuple[int, int], limit: int) -> tuple[np.ndarray, np.ndarray]:
    rows, columns = shape
    if rows * columns <= limit:
        return np.arange(rows, dtype=int), np.arange(columns, dtype=int)
    ratio = rows / max(columns, 1)
    row_limit = max(2, min(rows, int(math.sqrt(limit * ratio))))
    column_limit = max(2, min(columns, max(2, limit // row_limit)))
    while row_limit * column_limit > limit and column_limit > 2:
        column_limit -= 1
    return _sample_indices(rows, row_limit), _sample_indices(columns, column_limit)


def _display_limit() -> int:
    return max(100, int(getattr(settings, "FIELD_MAX_DISPLAY_POINTS", 12_000)))


@login_required
def field_workspace(request, analysis_id, run_id, section="overview"):
    analysis, run = _field_run(request.user, analysis_id, run_id)
    valid_sections = {key for key, _label in FIELD_SECTIONS}
    if section not in valid_sections:
        raise Http404
    if run.status != RunStatus.COMPLETED:
        return render(
            request,
            "analyses/field_workspace.html",
            _analysis_context(
                request,
                analysis,
                run=run,
                workspace_ready=False,
                field_sections=FIELD_SECTIONS,
                field_section=section,
            ),
        )
    try:
        with open_observable_field_result_reader(run, verify_hash=True) as reader:
            manifest = reader.read_manifest()
            t = reader.read_series("t")
            spatial_axes = [
                reader.read_series(f"spatial_axis_{index}")
                for index in range(len(manifest["spatial_shape"]))
            ]
    except (OSError, FieldResultArtifactError):
        return render(
            request,
            "analyses/field_workspace.html",
            _analysis_context(
                request,
                analysis,
                run=run,
                workspace_ready=False,
                result_error=_("The immutable observable field result could not be read safely."),
                field_sections=FIELD_SECTIONS,
                field_section=section,
            ),
        )
    selected_time = max(0, min(int(request.GET.get("time", 0)), len(t) - 1))
    spatial_index = _int_list(request.GET.get("spatial", ""))
    if len(spatial_index) != len(manifest["spatial_shape"]):
        spatial_index = tuple(0 for _ in manifest["spatial_shape"])
    axis_context = []
    for index, axis in enumerate(spatial_axes):
        meta = manifest.get("spatial_axes", [])[index]
        axis_context.append(
            {
                "dimension": index,
                "name": meta.get("name") or f"spatial_index_{index + 1}",
                "unit": meta.get("unit", ""),
                "length": int(axis.shape[0]),
                "selected_index": spatial_index[index],
                "selected_value": axis[spatial_index[index]],
            }
        )
    return render(
        request,
        "analyses/field_workspace.html",
        _analysis_context(
            request,
            analysis,
            run=run,
            artifact=run.result_artifact,
            workspace_ready=True,
            manifest=manifest,
            field_sections=FIELD_SECTIONS,
            field_section=section,
            selected_time=selected_time,
            selected_time_value=t[selected_time],
            selected_spatial=spatial_index,
            spatial_axes=axis_context,
            spatial_rank=len(manifest["spatial_shape"]),
            time_count=len(t),
            display_max_points=_display_limit(),
        ),
    )


@login_required
def field_manifest(request, analysis_id, run_id):
    _analysis, run = _field_run(request.user, analysis_id, run_id)
    try:
        with open_observable_field_result_reader(run) as reader:
            manifest = reader.read_manifest()
    except (OSError, FieldResultArtifactError) as exc:
        raise Http404 from exc
    return JsonResponse(manifest)


@login_required
def field_heatmap(request, analysis_id, run_id):
    """Return a display-only sampled time × 1D-space grid."""

    _analysis, run = _field_run(request.user, analysis_id, run_id)
    series = request.GET.get("series", "u")
    representation = request.GET.get("representation", "magnitude" if series in {"beta_obs", "b_obs"} else "value")
    try:
        with open_observable_field_result_reader(run) as reader:
            manifest = reader.read_manifest()
            if len(manifest["spatial_shape"]) != 1:
                raise FieldResultArtifactError("Time-space heatmaps require one spatial dimension.")
            data = reader.read_series(series)
            data = np.moveaxis(data, int(manifest["time_axis"]), 0)
            shown = _representation(data, representation)
            t = reader.read_series("t")
            x = reader.read_series("spatial_axis_0")
            time_indices, space_indices = _display_grid_indices(shown.shape, _display_limit())
            sampled = shown[np.ix_(time_indices, space_indices)]
    except (OSError, FieldResultArtifactError, KeyError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(
        {
            "series": series,
            "representation": representation,
            "display_only": True,
            "exact_shape": list(shown.shape),
            "time_indices": time_indices.tolist(),
            "space_indices": space_indices.tolist(),
            "time": np.asarray(t)[time_indices].tolist(),
            "space": np.asarray(x)[space_indices].tolist(),
            "values": sampled.tolist(),
        }
    )


@login_required
def field_slice(request, analysis_id, run_id):
    """Return an exact time slice with optional display-only index sampling."""

    _analysis, run = _field_run(request.user, analysis_id, run_id)
    series = request.GET.get("series", "u")
    representation = request.GET.get("representation", "magnitude" if series in {"beta_obs", "b_obs"} else "value")
    time_index = int(request.GET.get("time", 0))
    try:
        with open_observable_field_result_reader(run) as reader:
            manifest = reader.read_manifest()
            rank = len(manifest["spatial_shape"])
            default_dims = tuple(range(min(2, rank)))
            dimensions = _int_list(request.GET.get("dims", ",".join(str(v) for v in default_dims)))
            fixed = _fixed(request.GET.get("fixed", ""))
            exact = reader.spatial_slice(
                series,
                time_index=time_index,
                display_dimensions=dimensions,
                fixed_indices=fixed,
            )
            shown = _representation(exact, representation)
            axes = [reader.read_series(f"spatial_axis_{dimension}") for dimension in dimensions]
            if shown.ndim == 1:
                idx = _sample_indices(shown.shape[0], _display_limit())
                values = shown[idx]
                axis_values = [np.asarray(axes[0])[idx].tolist()]
                display_indices = [idx.tolist()]
            else:
                first, second = _display_grid_indices(shown.shape, _display_limit())
                values = shown[np.ix_(first, second)]
                axis_values = [np.asarray(axes[0])[first].tolist(), np.asarray(axes[1])[second].tolist()]
                display_indices = [first.tolist(), second.tolist()]
    except (OSError, FieldResultArtifactError, KeyError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(
        {
            "series": series,
            "representation": representation,
            "time_index": time_index,
            "display_dimensions": list(dimensions),
            "fixed_indices": fixed,
            "display_only": True,
            "exact_shape": list(shown.shape),
            "display_indices": display_indices,
            "axes": axis_values,
            "values": np.asarray(values).tolist(),
        }
    )


@login_required
def field_point(request, analysis_id, run_id):
    """Return exact full-resolution values for one space-time cell."""

    _analysis, run = _field_run(request.user, analysis_id, run_id)
    time_index = int(request.GET.get("time", 0))
    spatial = _int_list(request.GET.get("spatial", ""))
    names = ("u", "u_star", "X_star", "A_star", "M", "O", "D", "S", "J", "U", "beta_obs", "b_obs")
    try:
        with open_observable_field_result_reader(run) as reader:
            manifest = reader.read_manifest()
            if len(spatial) != len(manifest["spatial_shape"]):
                raise FieldResultArtifactError("Spatial index rank does not match the stored field.")
            t = reader.read_series("t")
            coordinates = []
            for dimension, index in enumerate(spatial):
                axis = reader.read_series(f"spatial_axis_{dimension}")
                if index < 0 or index >= axis.shape[0]:
                    raise FieldResultArtifactError("Requested spatial index is outside the stored field.")
                meta = manifest.get("spatial_axes", [])[dimension]
                coordinates.append(
                    {
                        "dimension": dimension,
                        "index": index,
                        "name": meta.get("name") or f"spatial_index_{dimension + 1}",
                        "unit": meta.get("unit", ""),
                        "value": _complex_value(axis[index]),
                    }
                )
            values = {
                name: _complex_value(reader.exact_point(name, time_index, spatial))
                for name in names
                if name in reader.available_series
            }
    except (OSError, FieldResultArtifactError, KeyError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(
        {
            "time_index": time_index,
            "time_value": _complex_value(t[time_index]),
            "spatial_index": list(spatial),
            "coordinates": coordinates,
            "values": values,
            "exact": True,
        }
    )


@login_required
def field_trace(request, analysis_id, run_id):
    """Return a display trace for one exact spatial trajectory."""

    _analysis, run = _field_run(request.user, analysis_id, run_id)
    spatial = _int_list(request.GET.get("spatial", ""))
    try:
        with open_observable_field_result_reader(run) as reader:
            manifest = reader.read_manifest()
            if len(spatial) != len(manifest["spatial_shape"]):
                raise FieldResultArtifactError("Spatial index rank does not match the stored field.")
            t = reader.read_series("t")
            u = reader.spatial_point_series("u", spatial)
            beta = reader.spatial_point_series("beta_obs", spatial)
            b = reader.spatial_point_series("b_obs", spatial)
            indices = _sample_indices(len(t), _display_limit())
    except (OSError, FieldResultArtifactError, KeyError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(
        {
            "spatial_index": list(spatial),
            "display_only": True,
            "exact_sample_count": int(len(t)),
            "indices": indices.tolist(),
            "time": np.asarray(t)[indices].tolist(),
            "u": np.asarray(u)[indices].tolist(),
            "beta_obs": {
                "real": np.real(beta)[indices].tolist(),
                "imag": np.imag(beta)[indices].tolist(),
                "magnitude": np.abs(beta)[indices].tolist(),
                "phase": np.angle(beta)[indices].tolist(),
            },
            "b_obs": {
                "real": np.real(b)[indices].tolist(),
                "imag": np.imag(b)[indices].tolist(),
                "magnitude": np.abs(b)[indices].tolist(),
                "phase": np.angle(b)[indices].tolist(),
            },
        }
    )
