"""Private visualization views for completed multivariate AnalysisRuns."""

from __future__ import annotations

import math

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _

from workspaces.permissions import can_view_analysis_result

from .models import AnalysisKind, AnalysisResultArtifact, RunStatus
from .multivariate_results import MultivariateResultArtifactError
from .multivariate_visualization import (
    AggregateResultAdapter,
    ComponentResultAdapter,
    aggregate_manifest_payload,
    aggregate_sample_payload,
    aggregate_series_payload,
    aggregate_table_payload,
    component_manifest_payload,
    component_sample_payload,
    component_series_payload,
    component_table_payload,
)
from .storage import analysis_storage, open_multivariate_result_reader
from .views import _analysis_context, _run_or_404

MULTIVARIATE_SECTIONS = (
    ("overview", _("Overview")),
    ("component", _("Component Results")),
    ("aggregate", _("Lab Multivariate Result")),
    ("table", _("Exact Table")),
    ("reproducibility", _("Reproducibility")),
)
SECTION_KEYS = {key for key, _label in MULTIVARIATE_SECTIONS}


def _private_json(payload: dict, *, status: int = 200) -> JsonResponse:
    response = JsonResponse(payload, status=status, json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "private, no-store"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _require_multivariate_result(request, analysis_id, run_id):
    analysis, run = _run_or_404(request.user, analysis_id, run_id)
    if analysis.analysis_kind != AnalysisKind.MULTIVARIATE:
        raise Http404
    if not can_view_analysis_result(request.user, run):
        raise Http404
    artifact = AnalysisResultArtifact.objects.filter(run=run).first()
    ready = bool(
        run.status == RunStatus.COMPLETED
        and artifact is not None
        and analysis_storage().exists(artifact.storage_path)
    )
    return analysis, run, artifact, ready


def _component_position(request, positions: tuple[int, ...]) -> int:
    if not positions:
        raise Http404
    try:
        requested = int(request.GET.get("component", positions[0]))
    except (TypeError, ValueError):
        requested = positions[0]
    return requested if requested in positions else positions[0]


def _sample_index(request, count: int) -> int:
    if count <= 0:
        return 0
    try:
        index = int(request.GET.get("sample", "0"))
    except (TypeError, ValueError):
        index = 0
    return min(max(index, 0), count - 1)


def _power_unit(components: list[dict]) -> str:
    if not components:
        return ""
    return str(
        ((components[0].get("parameter_snapshot") or {}).get("P_c") or {}).get("unit")
        or ""
    )


@login_required
def multivariate_workspace(request, analysis_id, run_id, section="overview"):
    if section not in SECTION_KEYS:
        raise Http404
    analysis, run, artifact, ready = _require_multivariate_result(
        request,
        analysis_id,
        run_id,
    )
    manifest = {}
    table = None
    result_error = ""
    sample_count = 0
    selected_component = 1
    component_inventory: list[dict] = []
    coordinate_mapping = run.mapping_snapshot.get("time") or {}
    coordinate_unit = str(coordinate_mapping.get("unit") or "")
    if ready:
        try:
            with open_multivariate_result_reader(run) as reader:
                manifest = reader.read_manifest()
                sample_count = reader.sample_count
                component_inventory = list(manifest.get("components") or [])
                positions = reader.component_positions
                selected_component = _component_position(request, positions)
                if section == "table":
                    page_size = settings.VISUALIZATION_TABLE_PAGE_SIZE
                    page_count = max(1, math.ceil(sample_count / page_size))
                    try:
                        page = int(request.GET.get("page", "1"))
                    except (TypeError, ValueError):
                        page = 1
                    page = min(max(page, 1), page_count)
                    start = (page - 1) * page_size
                    stop = min(start + page_size, sample_count)
                    adapter = ComponentResultAdapter(
                        reader,
                        position=selected_component,
                        coordinate_unit=coordinate_unit,
                    )
                    table = component_table_payload(
                        adapter,
                        start=start,
                        stop=stop,
                        result_sha256=artifact.sha256,
                    )
                    table.update(
                        {
                            "page": page,
                            "page_count": page_count,
                            "has_previous": page > 1,
                            "has_next": page < page_count,
                            "previous_page": page - 1,
                            "next_page": page + 1,
                        }
                    )
        except (OSError, MultivariateResultArtifactError, IndexError, KeyError, ValueError):
            ready = False
            result_error = _(
                "The stored multivariate result cannot be read safely. Studio will not reconstruct or repair it."
            )
    selected_sample = _sample_index(request, sample_count)
    selected_descriptor = next(
        (
            item
            for item in component_inventory
            if int(item.get("position", -1)) == selected_component
        ),
        None,
    )
    return render(
        request,
        "analyses/multivariate_results_workspace.html",
        _analysis_context(
            request,
            analysis,
            run=run,
            artifact=artifact,
            workspace_ready=ready,
            result_error=result_error,
            result_sections=MULTIVARIATE_SECTIONS,
            result_section=section,
            manifest=manifest,
            component_inventory=component_inventory,
            selected_component=selected_component,
            selected_component_descriptor=selected_descriptor,
            selected_sample=selected_sample,
            sample_count=sample_count,
            coordinate_label=coordinate_mapping.get("display_name")
            or coordinate_mapping.get("source_name")
            or _("Coordinate"),
            coordinate_unit=coordinate_unit,
            display_max_points=settings.VISUALIZATION_MAX_POINTS,
            table=table,
        ),
    )


def _component_adapter(request, analysis_id, run_id, position):
    analysis, run, artifact, ready = _require_multivariate_result(
        request,
        analysis_id,
        run_id,
    )
    if not ready:
        return analysis, run, artifact, None, None
    reader_cm = open_multivariate_result_reader(run)
    reader = reader_cm.__enter__()
    if int(position) not in reader.component_positions:
        reader_cm.__exit__(None, None, None)
        raise Http404
    coordinate = run.mapping_snapshot.get("time") or {}
    adapter = ComponentResultAdapter(
        reader,
        position=int(position),
        coordinate_unit=str(coordinate.get("unit") or ""),
    )
    return analysis, run, artifact, reader_cm, adapter


@login_required
def component_manifest(request, analysis_id, run_id, position):
    if request.method != "GET":
        raise Http404
    _analysis, _run, artifact, reader_cm, adapter = _component_adapter(
        request, analysis_id, run_id, position
    )
    if adapter is None:
        return _private_json({"error": _("Multivariate result is not available.")}, status=409)
    try:
        return _private_json(
            component_manifest_payload(adapter, result_sha256=artifact.sha256)
        )
    finally:
        reader_cm.__exit__(None, None, None)


@login_required
def component_series(request, analysis_id, run_id, position):
    if request.method != "GET":
        raise Http404
    _analysis, _run, artifact, reader_cm, adapter = _component_adapter(
        request, analysis_id, run_id, position
    )
    if adapter is None:
        return _private_json({"error": _("Multivariate result is not available.")}, status=409)
    try:
        names = tuple(
            item.strip()
            for item in request.GET.get("series", "").split(",")
            if item.strip()
        )
        if not names or len(names) > 8 or len(names) != len(set(names)):
            return _private_json({"error": _("Select one to eight unique stored series.")}, status=400)
        start = int(request.GET.get("start", "0"))
        stop_text = request.GET.get("stop")
        stop = int(stop_text) if stop_text not in {None, ""} else None
        requested = int(request.GET.get("max_points", settings.VISUALIZATION_MAX_POINTS))
        payload = component_series_payload(
            adapter,
            names=names,
            start=start,
            stop=stop,
            max_points=min(max(requested, 2), settings.VISUALIZATION_MAX_POINTS),
            result_sha256=artifact.sha256,
        )
        return _private_json(payload)
    except (KeyError, IndexError, TypeError, ValueError, MultivariateResultArtifactError):
        return _private_json({"error": _("Invalid component visualization request.")}, status=400)
    finally:
        reader_cm.__exit__(None, None, None)


@login_required
def component_sample(request, analysis_id, run_id, position):
    if request.method != "GET":
        raise Http404
    _analysis, _run, artifact, reader_cm, adapter = _component_adapter(
        request, analysis_id, run_id, position
    )
    if adapter is None:
        return _private_json({"error": _("Multivariate result is not available.")}, status=409)
    try:
        index = int(request.GET.get("index", "0"))
        return _private_json(
            component_sample_payload(
                adapter,
                index=index,
                result_sha256=artifact.sha256,
            )
        )
    except (IndexError, TypeError, ValueError, MultivariateResultArtifactError):
        return _private_json({"error": _("Invalid sample index.")}, status=400)
    finally:
        reader_cm.__exit__(None, None, None)


def _aggregate_adapter(request, analysis_id, run_id):
    analysis, run, artifact, ready = _require_multivariate_result(
        request,
        analysis_id,
        run_id,
    )
    if not ready:
        return analysis, run, artifact, None, None
    reader_cm = open_multivariate_result_reader(run)
    reader = reader_cm.__enter__()
    manifest = reader.read_manifest()
    coordinate = run.mapping_snapshot.get("time") or {}
    adapter = AggregateResultAdapter(
        reader,
        coordinate_unit=str(coordinate.get("unit") or ""),
        power_unit=_power_unit(list(manifest.get("components") or [])),
    )
    return analysis, run, artifact, reader_cm, adapter


@login_required
def aggregate_manifest(request, analysis_id, run_id):
    _analysis, _run, artifact, reader_cm, adapter = _aggregate_adapter(
        request, analysis_id, run_id
    )
    if adapter is None:
        return _private_json({"error": _("Multivariate result is not available.")}, status=409)
    try:
        return _private_json(aggregate_manifest_payload(adapter, result_sha256=artifact.sha256))
    finally:
        reader_cm.__exit__(None, None, None)


@login_required
def aggregate_series(request, analysis_id, run_id):
    _analysis, _run, artifact, reader_cm, adapter = _aggregate_adapter(
        request, analysis_id, run_id
    )
    if adapter is None:
        return _private_json({"error": _("Multivariate result is not available.")}, status=409)
    try:
        names = tuple(
            item.strip()
            for item in request.GET.get("series", "").split(",")
            if item.strip()
        )
        start = int(request.GET.get("start", "0"))
        stop_text = request.GET.get("stop")
        stop = int(stop_text) if stop_text not in {None, ""} else None
        requested = int(request.GET.get("max_points", settings.VISUALIZATION_MAX_POINTS))
        return _private_json(
            aggregate_series_payload(
                adapter,
                names=names,
                start=start,
                stop=stop,
                max_points=min(max(requested, 2), settings.VISUALIZATION_MAX_POINTS),
                result_sha256=artifact.sha256,
            )
        )
    except (KeyError, IndexError, TypeError, ValueError, MultivariateResultArtifactError):
        return _private_json({"error": _("Invalid aggregate visualization request.")}, status=400)
    finally:
        reader_cm.__exit__(None, None, None)


@login_required
def aggregate_sample(request, analysis_id, run_id):
    _analysis, _run, artifact, reader_cm, adapter = _aggregate_adapter(
        request, analysis_id, run_id
    )
    if adapter is None:
        return _private_json({"error": _("Multivariate result is not available.")}, status=409)
    try:
        index = int(request.GET.get("index", "0"))
        return _private_json(
            aggregate_sample_payload(
                adapter,
                index=index,
                result_sha256=artifact.sha256,
            )
        )
    except (IndexError, TypeError, ValueError, MultivariateResultArtifactError):
        return _private_json({"error": _("Invalid sample index.")}, status=400)
    finally:
        reader_cm.__exit__(None, None, None)
