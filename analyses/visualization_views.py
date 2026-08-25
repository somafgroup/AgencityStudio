"""Private server-rendered and JSON views for completed canonical Analysis results."""

from __future__ import annotations

import math

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _

from workspaces.permissions import can_view_analysis_result

from .models import AnalysisResultArtifact, RunStatus
from .results import ResultArtifactError
from .storage import analysis_storage, open_analysis_result_reader
from .views import _analysis_context, _run_or_404
from .visualization import (
    SECTION_SERIES,
    exact_table_payload,
    manifest_payload,
    sample_payload,
    series_payload,
)

RESULT_SECTIONS = (
    ("overview", _("Overview")),
    ("observable", _("Observable")),
    ("dynamics", _("Dynamics")),
    ("structure", _("Structure")),
    ("orientation", _("Contrast & Orientation")),
    ("beta", _("Agencity State")),
    ("flux", _("Agencity Flux")),
    ("table", _("Exact table")),
    ("reproducibility", _("Reproducibility")),
)
RESULT_SECTION_KEYS = {key for key, _label in RESULT_SECTIONS}


def _private_json(payload: dict, *, status: int = 200) -> JsonResponse:
    response = JsonResponse(payload, status=status, json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "private, no-store"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _result_artifact(run):
    return AnalysisResultArtifact.objects.filter(run=run).first()


def _artifact_ready(run, artifact) -> bool:
    return bool(
        run.status == RunStatus.COMPLETED
        and artifact is not None
        and analysis_storage().exists(artifact.storage_path)
    )


def _require_result_access(request, analysis_id, run_id):
    analysis, run = _run_or_404(request.user, analysis_id, run_id)
    if not can_view_analysis_result(request.user, run):
        raise Http404
    artifact = _result_artifact(run)
    if not _artifact_ready(run, artifact):
        return analysis, run, artifact, None
    return analysis, run, artifact, artifact


def _sample_index(request, sample_count: int) -> int:
    if sample_count <= 0:
        return 0
    try:
        index = int(request.GET.get("sample", "0"))
    except (TypeError, ValueError):
        return 0
    return min(max(index, 0), sample_count - 1)


@login_required
def result_workspace(request, analysis_id, run_id, section="overview"):
    """Render one deep-linkable scientific exploration section for an immutable Run."""
    if section not in RESULT_SECTION_KEYS:
        raise Http404
    analysis, run, artifact, ready_artifact = _require_result_access(
        request, analysis_id, run_id
    )
    runs = analysis.runs.order_by("-run_number")
    workspace_ready = False
    manifest = {}
    available_series: set[str] = set()
    sample_count = 0
    result_error = ""
    table = None

    if ready_artifact is not None:
        try:
            with open_analysis_result_reader(run) as reader:
                manifest = manifest_payload(reader, result_sha256=ready_artifact.sha256)
                available_series = set(reader.available_series)
                sample_count = reader.sample_count
                workspace_ready = True
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
                    table = exact_table_payload(
                        reader,
                        start=start,
                        stop=stop,
                        result_sha256=ready_artifact.sha256,
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
        except (OSError, ResultArtifactError, IndexError, KeyError, ValueError):
            workspace_ready = False
            result_error = _(
                "The stored canonical result cannot be read safely. Studio will not reconstruct or repair it."
            )

    requested_series = SECTION_SERIES.get(section, ())
    section_available = not requested_series or any(
        name in available_series for name in requested_series
    )
    selected_sample = _sample_index(request, sample_count)
    coordinate_mapping = run.mapping_snapshot.get("time") or {}
    coordinate_label = coordinate_mapping.get("display_name") or coordinate_mapping.get("source_name")
    coordinate_label = coordinate_label or _("Coordinate")
    coordinate_unit = coordinate_mapping.get("unit") or (manifest.get("units") or {}).get("coordinate")

    return render(
        request,
        "analyses/results_workspace.html",
        _analysis_context(
            request,
            analysis,
            run=run,
            runs=runs,
            artifact=artifact,
            workspace_ready=workspace_ready,
            result_error=result_error,
            result_sections=RESULT_SECTIONS,
            result_section=section,
            section_available=section_available,
            available_series=available_series,
            manifest=manifest,
            sample_count=sample_count,
            selected_sample=selected_sample,
            coordinate_label=coordinate_label,
            coordinate_unit=coordinate_unit,
            display_max_points=settings.VISUALIZATION_MAX_POINTS,
            table=table,
        ),
    )


@login_required
def visualization_manifest(request, analysis_id, run_id):
    if request.method != "GET":
        raise Http404
    _analysis, run, artifact, ready_artifact = _require_result_access(
        request, analysis_id, run_id
    )
    if ready_artifact is None:
        return _private_json({"error": _("Canonical result is not available.")}, status=409)
    try:
        with open_analysis_result_reader(run) as reader:
            payload = manifest_payload(reader, result_sha256=artifact.sha256)
    except (OSError, ResultArtifactError):
        return _private_json({"error": _("Stored canonical result is unavailable or corrupt.")}, status=422)
    return _private_json(payload)


@login_required
def visualization_series(request, analysis_id, run_id):
    if request.method != "GET":
        raise Http404
    _analysis, run, artifact, ready_artifact = _require_result_access(
        request, analysis_id, run_id
    )
    if ready_artifact is None:
        return _private_json({"error": _("Canonical result is not available.")}, status=409)

    raw_names = [item.strip() for item in request.GET.get("series", "").split(",") if item.strip()]
    if not raw_names or len(raw_names) > 8 or len(raw_names) != len(set(raw_names)):
        return _private_json({"error": _("Select between one and eight unique stored series.")}, status=400)
    try:
        start = int(request.GET.get("start", "0"))
        stop_text = request.GET.get("stop")
        stop = int(stop_text) if stop_text not in {None, ""} else None
        requested_points = int(request.GET.get("max_points", settings.VISUALIZATION_MAX_POINTS))
    except (TypeError, ValueError):
        return _private_json({"error": _("Invalid visualization range.")}, status=400)
    max_points = min(max(requested_points, 2), settings.VISUALIZATION_MAX_POINTS)

    try:
        with open_analysis_result_reader(run) as reader:
            payload = series_payload(
                reader,
                names=tuple(raw_names),
                start=start,
                stop=stop,
                max_points=max_points,
                result_sha256=artifact.sha256,
            )
    except KeyError:
        return _private_json({"error": _("One requested canonical series is unavailable.")}, status=404)
    except (IndexError, ValueError):
        return _private_json({"error": _("Invalid visualization range.")}, status=400)
    except (OSError, ResultArtifactError):
        return _private_json({"error": _("Stored canonical result is unavailable or corrupt.")}, status=422)
    return _private_json(payload)


@login_required
def visualization_sample(request, analysis_id, run_id):
    if request.method != "GET":
        raise Http404
    _analysis, run, artifact, ready_artifact = _require_result_access(
        request, analysis_id, run_id
    )
    if ready_artifact is None:
        return _private_json({"error": _("Canonical result is not available.")}, status=409)
    try:
        index = int(request.GET.get("index", "0"))
    except (TypeError, ValueError):
        return _private_json({"error": _("Invalid sample index.")}, status=400)
    try:
        with open_analysis_result_reader(run) as reader:
            payload = sample_payload(reader, index=index, result_sha256=artifact.sha256)
    except IndexError:
        return _private_json({"error": _("Sample index is outside the stored result.")}, status=400)
    except (OSError, ResultArtifactError):
        return _private_json({"error": _("Stored canonical result is unavailable or corrupt.")}, status=422)
    return _private_json(payload)
