"""Private display-only endpoints for immutable autonomous RESEARCH field results."""

import math

import numpy as np
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _

from .models import RunStatus
from .research_contract import RESEARCH_ANALYSIS_KIND
from .research_results import ResearchArtifactError
from .research_storage import open_research_input_reader, open_research_result_reader
from .views import _analysis_context, _run_or_404


BASE_SECTIONS = (
    ("overview", _("Overview")),
    ("initial", _("Initial Condition")),
    ("dynamics", _("Dynamics")),
    ("field", _("Field State")),
)


def _research_run(user, analysis_id, run_id):
    analysis, run = _run_or_404(user, analysis_id, run_id)
    if analysis.analysis_kind != RESEARCH_ANALYSIS_KIND:
        raise Http404
    return analysis, run


def _sections(manifest: dict):
    sections = list(BASE_SECTIONS)
    derived = set(manifest.get("derived_public_outputs") or [])
    if "phase_winding" in derived:
        sections.append(("topology", _("Topology")))
    if derived.intersection(
        {"field_agencial_entropy", "total_dissipated_power", "total_entropy_production"}
    ):
        sections.append(("thermodynamics", _("Thermodynamics")))
    sections.append(("reproducibility", _("Reproducibility")))
    return tuple(sections)


def _indices(value: str) -> tuple[int, ...]:
    if not str(value or "").strip():
        return ()
    try:
        return tuple(int(item.strip()) for item in str(value).split(",") if item.strip())
    except ValueError as exc:
        raise ResearchArtifactError("Spatial indices must be comma-separated integers.") from exc


def _fixed(value: str) -> dict[int, int]:
    fixed = {}
    if not str(value or "").strip():
        return fixed
    try:
        for item in str(value).split(","):
            dimension, index = item.split(":", 1)
            fixed[int(dimension.strip())] = int(index.strip())
    except ValueError as exc:
        raise ResearchArtifactError("Fixed dimensions must use dimension:index pairs.") from exc
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
    return float(scalar)


def _representation(array, mode: str):
    data = np.asarray(array)
    if np.iscomplexobj(data):
        if mode == "real":
            return np.real(data)
        if mode == "imag":
            return np.imag(data)
        if mode == "magnitude":
            return np.abs(data)
        if mode == "phase":
            return np.angle(data)
        raise ResearchArtifactError("Unknown complex display representation.")
    if mode not in {"value", "real", "magnitude"}:
        raise ResearchArtifactError("This display representation requires a complex field.")
    return np.asarray(data, dtype=float)


def _sample_indices(length: int, maximum: int):
    if length <= maximum:
        return np.arange(length, dtype=int)
    return np.unique(np.linspace(0, length - 1, maximum, dtype=int))


def _display_grid_indices(shape: tuple[int, int], limit: int):
    rows, columns = shape
    if rows * columns <= limit:
        return np.arange(rows, dtype=int), np.arange(columns, dtype=int)
    ratio = rows / max(columns, 1)
    row_limit = max(2, min(rows, int(math.sqrt(limit * ratio))))
    column_limit = max(2, min(columns, max(2, limit // row_limit)))
    return _sample_indices(rows, row_limit), _sample_indices(columns, column_limit)


def _display_limit():
    return max(100, int(getattr(settings, "RESEARCH_FIELD_MAX_DISPLAY_POINTS", 12_000)))


@login_required
def research_workspace(request, analysis_id, run_id, section="overview"):
    analysis, run = _research_run(request.user, analysis_id, run_id)
    if run.status != RunStatus.COMPLETED:
        return render(
            request,
            "analyses/research_workspace.html",
            _analysis_context(
                request,
                analysis,
                run=run,
                workspace_ready=False,
                research_sections=(("overview", _("Overview")),),
                research_section="overview",
            ),
        )
    try:
        with open_research_result_reader(run, verify_hash=True) as reader:
            manifest = reader.read_manifest()
            times = reader.read_series("times")
            spatial_shape = tuple(int(value) for value in manifest["spatial_shape"])
            axes = [reader.read_series(f"spatial_axis_{i}") for i in range(len(spatial_shape))]
        with open_research_input_reader(run, verify_hash=True) as input_reader:
            input_manifest = input_reader.read_manifest()
    except (OSError, ResearchArtifactError):
        return render(
            request,
            "analyses/research_workspace.html",
            _analysis_context(
                request,
                analysis,
                run=run,
                workspace_ready=False,
                result_error=_("The immutable RESEARCH field artifacts could not be read safely."),
                research_sections=(("overview", _("Overview")),),
                research_section="overview",
            ),
        )
    sections = _sections(manifest)
    if section not in {key for key, _label in sections}:
        raise Http404
    selected_time = max(0, min(int(request.GET.get("time", 0)), len(times) - 1))
    spatial = _indices(request.GET.get("spatial", ""))
    if len(spatial) != len(spatial_shape):
        spatial = tuple(0 for _ in spatial_shape)
    axis_context = [
        {
            "dimension": index,
            "length": int(axis.size),
            "selected_index": spatial[index],
            "selected_value": float(axis[spatial[index]]),
            "origin": float(axis[0]),
            "end": float(axis[-1]),
            "spacing": float(axis[1] - axis[0]),
        }
        for index, axis in enumerate(axes)
    ]
    return render(
        request,
        "analyses/research_workspace.html",
        _analysis_context(
            request,
            analysis,
            run=run,
            artifact=run.result_artifact,
            input_artifact=run.research_input_artifact,
            workspace_ready=True,
            manifest=manifest,
            input_manifest=input_manifest,
            research_sections=sections,
            research_section=section,
            selected_time=selected_time,
            selected_time_value=float(times[selected_time]),
            selected_spatial=spatial,
            spatial_axes=axis_context,
            spatial_rank=len(spatial_shape),
            time_count=len(times),
        ),
    )


@login_required
def research_manifest(request, analysis_id, run_id):
    _analysis, run = _research_run(request.user, analysis_id, run_id)
    try:
        with open_research_result_reader(run) as reader:
            manifest = reader.read_manifest()
    except (OSError, ResearchArtifactError) as exc:
        raise Http404 from exc
    return JsonResponse(manifest)


@login_required
def research_slice(request, analysis_id, run_id):
    _analysis, run = _research_run(request.user, analysis_id, run_id)
    time_index = int(request.GET.get("time", 0))
    representation = request.GET.get("representation", "magnitude")
    try:
        with open_research_result_reader(run) as reader:
            manifest = reader.read_manifest()
            rank = len(manifest["spatial_shape"])
            default_dims = tuple(range(min(2, rank)))
            dimensions = _indices(
                request.GET.get("dims", ",".join(str(value) for value in default_dims))
            )
            fixed = _fixed(request.GET.get("fixed", ""))
            exact = reader.spatial_slice(
                "phi",
                time_index=time_index,
                display_dimensions=dimensions,
                fixed_indices=fixed,
            )
            shown = _representation(exact, representation)
            axes = [reader.read_series(f"spatial_axis_{dimension}") for dimension in dimensions]
            if shown.ndim == 1:
                first = _sample_indices(shown.shape[0], _display_limit())
                values = shown[first]
                axis_values = [np.asarray(axes[0])[first].tolist()]
                display_indices = [first.tolist()]
            else:
                first, second = _display_grid_indices(shown.shape, _display_limit())
                values = shown[np.ix_(first, second)]
                axis_values = [
                    np.asarray(axes[0])[first].tolist(),
                    np.asarray(axes[1])[second].tolist(),
                ]
                display_indices = [first.tolist(), second.tolist()]
    except (OSError, ResearchArtifactError, KeyError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(
        {
            "series": "phi",
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
def research_point(request, analysis_id, run_id):
    _analysis, run = _research_run(request.user, analysis_id, run_id)
    time_index = int(request.GET.get("time", 0))
    spatial = _indices(request.GET.get("spatial", ""))
    try:
        with open_research_result_reader(run) as reader:
            manifest = reader.read_manifest()
            if len(spatial) != len(manifest["spatial_shape"]):
                raise ResearchArtifactError("Spatial index rank does not match the stored field.")
            times = reader.read_series("times")
            phi = reader.exact_point("phi", time_index, spatial)
            phi_dot = (
                reader.exact_point("phi_dot", time_index, spatial)
                if "phi_dot" in reader.available_series
                else None
            )
            coordinates = []
            for dimension, index in enumerate(spatial):
                axis = reader.read_series(f"spatial_axis_{dimension}")
                if index < 0 or index >= axis.size:
                    raise ResearchArtifactError("Requested spatial index is outside the stored field.")
                coordinates.append(
                    {"dimension": dimension, "index": index, "value": float(axis[index])}
                )
    except (OSError, ResearchArtifactError, KeyError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(
        {
            "time_index": time_index,
            "time_value": float(times[time_index]),
            "spatial_index": list(spatial),
            "coordinates": coordinates,
            "phi": _complex_value(phi),
            "phi_dot": None if phi_dot is None else _complex_value(phi_dot),
            "exact": True,
        }
    )


@login_required
def research_trace(request, analysis_id, run_id):
    _analysis, run = _research_run(request.user, analysis_id, run_id)
    spatial = _indices(request.GET.get("spatial", ""))
    try:
        with open_research_result_reader(run) as reader:
            manifest = reader.read_manifest()
            if len(spatial) != len(manifest["spatial_shape"]):
                raise ResearchArtifactError("Spatial index rank does not match the stored field.")
            times = reader.read_series("times")
            phi = reader.spatial_point_series("phi", spatial)
            shown = _sample_indices(len(times), _display_limit())
    except (OSError, ResearchArtifactError, KeyError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(
        {
            "spatial_index": list(spatial),
            "display_only": True,
            "exact_sample_count": len(times),
            "indices": shown.tolist(),
            "time": np.asarray(times)[shown].tolist(),
            "phi": {
                "real": np.real(phi)[shown].tolist(),
                "imag": np.imag(phi)[shown].tolist(),
                "magnitude": np.abs(phi)[shown].tolist(),
                "phase": np.angle(phi)[shown].tolist(),
            },
        }
    )


@login_required
def research_derived(request, analysis_id, run_id):
    _analysis, run = _research_run(request.user, analysis_id, run_id)
    requested = request.GET.get("series", "phase_winding")
    allowed = {
        "phase_winding",
        "field_agencial_entropy",
        "total_dissipated_power",
        "total_entropy_production",
    }
    if requested not in allowed:
        return JsonResponse({"error": "Unsupported stored public Research quantity."}, status=400)
    try:
        with open_research_result_reader(run) as reader:
            if requested not in reader.available_series:
                raise ResearchArtifactError("Requested public Research output was not computed for this Run.")
            times = reader.read_series("times")
            values = reader.read_series(requested)
            shown = _sample_indices(len(times), _display_limit())
    except (OSError, ResearchArtifactError, KeyError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(
        {
            "series": requested,
            "display_only": True,
            "indices": shown.tolist(),
            "time": np.asarray(times)[shown].tolist(),
            "values": np.asarray(values)[shown].tolist(),
        }
    )
