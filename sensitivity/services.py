"""Transactional lifecycle services for immutable sensitivity studies."""

from __future__ import annotations

import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.http import Http404
from django.utils import timezone
from django.utils.translation import gettext as _

from analyses.models import AnalysisResultArtifact, AnalysisRun, RunStatus
from analyses.services import software_context
from analyses.sources import descriptor_for, materialize_vectors
from analyses.storage import analysis_storage
from labbridge.sensitivity import TAU_MULTISCALE_API, WINDOW_SENSITIVITY_API
from projects.models import ProjectActivity
from workspaces.permissions import can_run_analysis, can_view_analysis_result

from .configuration import validate_grid_against_run
from .models import GridType, SensitivityStudy, StudyStatus, StudyType
from .results import SENSITIVITY_SCHEMA_VERSION


def _fingerprint(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _record(study: SensitivityStudy, *, event: str, detail: str) -> None:
    run = study.analysis_run
    ProjectActivity.objects.create(
        project=run.analysis.project,
        actor=study.created_by,
        event=event,
        detail=detail[:255],
    )


def _enqueue(study_id) -> None:
    from .tasks import execute_sensitivity_study

    execute_sensitivity_study.delay(str(study_id))


def _review_base_run(run: AnalysisRun) -> AnalysisResultArtifact:
    if run.status != RunStatus.COMPLETED:
        raise ValidationError(_("Sensitivity studies require a completed canonical AnalysisRun."))
    if not run.result_sha256:
        raise ValidationError(_("The canonical Run has no pinned result SHA-256."))
    try:
        artifact = run.result_artifact
    except AnalysisResultArtifact.DoesNotExist as exc:
        raise ValidationError(_("The canonical result artifact is unavailable.")) from exc
    if artifact.sha256 != run.result_sha256:
        raise ValidationError(_("The canonical result hash does not match its artifact provenance."))
    if not analysis_storage().exists(artifact.storage_path):
        raise ValidationError(_("The canonical result artifact is missing from private storage."))
    return artifact


def _materialize(run: AnalysisRun):
    time_mapping = run.mapping_snapshot["time"]
    observable_mapping = run.mapping_snapshot["observable"]
    xi, u = materialize_vectors(
        dataset_version=run.source_dataset_version,
        prepared_artifact=run.source_prepared_artifact,
        coordinate_position=int(time_mapping["position"]),
        observable_position=int(observable_mapping["position"]),
    )
    descriptor = descriptor_for(
        dataset_version=run.source_dataset_version,
        prepared_artifact=run.source_prepared_artifact,
    )
    if descriptor.sha256 != run.source_sha256:
        raise ValidationError(_("The pinned source SHA-256 no longer matches the AnalysisRun."))
    return xi, u


def sensitivity_review_snapshot(*, run: AnalysisRun, configuration: dict) -> dict:
    """Validate and return the exact immutable contract shown before execution."""
    artifact = _review_base_run(run)
    context = software_context()
    if context["agencitylab_version"] != run.agencitylab_version:
        raise ValidationError(
            _("Sensitivity studies require the same AgencityLab version as the canonical Run.")
        )
    if context["agencitylab_version"] != "1.1.3":
        raise ValidationError(_("AgencityLab 1.1.3 is required for the Plan 10 contract."))

    study_type = str(configuration.get("study_type") or "")
    grid_type = str(configuration.get("grid_type") or "")
    grid = [float(value) for value in configuration.get("requested_grid") or []]
    if study_type not in StudyType.values:
        raise ValidationError(_("Unsupported sensitivity study type."))
    if grid_type not in GridType.values:
        raise ValidationError(_("Unsupported sensitivity grid type."))
    if not grid:
        raise ValidationError(_("Sensitivity studies require an explicit non-empty scale grid."))

    params = run.parameter_snapshot
    expected_unit = str(params["tau"].get("unit") or "")
    grid_unit = str(configuration.get("grid_unit") or "")
    if not expected_unit or grid_unit != expected_unit:
        raise ValidationError(
            _("Scale values must use the exact coordinate/tau unit of the canonical Run; Studio performs no hidden unit conversion.")
        )

    xi, u = _materialize(run)
    try:
        validate_grid_against_run(study_type=study_type, grid=grid, xi=xi, u=u, run=run)
    except Exception as exc:
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError(str(exc)) from exc

    api_identifier = (
        TAU_MULTISCALE_API if study_type == StudyType.TAU_MULTISCALE else WINDOW_SENSITIVITY_API
    )
    requested_w_mode = str(params["w"].get("mode") or "UNSPECIFIED")
    requested_w = params["w"].get("requested_value")
    fixed = {
        "A_ref": dict(params["A_ref"]),
        "P_c": dict(params["P_c"]),
        "base_tau": dict(params["tau"]),
        "base_w": dict(params["w"]),
        "source_sha256": run.source_sha256,
        "system_revision_id": str(run.system_revision_id),
        "system_configuration_fingerprint": run.system_configuration_fingerprint,
        "mapping_snapshot": run.mapping_snapshot,
    }
    semantics = {
        "varied_parameter": "tau" if study_type == StudyType.TAU_MULTISCALE else "w",
        "requested_w_mode": requested_w_mode,
        "requested_w": requested_w,
        "tau_fixed": study_type == StudyType.W_SENSITIVITY,
        "A_ref_fixed": True,
        "P_c_fixed": True,
        "source_fixed": True,
        "no_parameter_promotion": True,
    }
    return {
        "run": run,
        "canonical_artifact": artifact,
        "configuration": {
            **configuration,
            "requested_grid": grid,
            "semantics": semantics,
        },
        "fixed_parameter_snapshot": fixed,
        "public_api_identifier": api_identifier,
        "software": context,
    }


def _next_number(run: AnalysisRun) -> int:
    latest = SensitivityStudy.objects.filter(analysis_run=run).aggregate(value=Max("study_number"))[
        "value"
    ]
    return (latest or 0) + 1


@transaction.atomic
def queue_sensitivity_study(*, actor, run: AnalysisRun, configuration: dict) -> SensitivityStudy:
    """Pin one completed canonical Run and queue a new immutable sensitivity study."""
    locked = (
        AnalysisRun.objects.select_for_update()
        .select_related(
            "analysis",
            "analysis__project",
            "analysis__project__workspace",
            "system_revision",
            "source_dataset_version",
            "source_prepared_artifact",
        )
        .get(pk=run.pk)
    )
    if not can_run_analysis(actor, locked.analysis):
        raise PermissionDenied
    snapshot = sensitivity_review_snapshot(run=locked, configuration=configuration)
    context = snapshot["software"]
    normalized = snapshot["configuration"]
    fixed = snapshot["fixed_parameter_snapshot"]
    payload = {
        "canonical_run_id": str(locked.pk),
        "canonical_result_sha256": locked.result_sha256,
        "source_sha256": locked.source_sha256,
        "study_type": normalized["study_type"],
        "grid_type": normalized["grid_type"],
        "grid_unit": normalized["grid_unit"],
        "requested_grid": normalized["requested_grid"],
        "fixed_parameter_snapshot": fixed,
        "public_api_identifier": snapshot["public_api_identifier"],
        "agencitylab_version": context["agencitylab_version"],
        "schema_version": SENSITIVITY_SCHEMA_VERSION,
    }
    study = SensitivityStudy.objects.create(
        analysis_run=locked,
        study_number=_next_number(locked),
        study_type=normalized["study_type"],
        status=StudyStatus.QUEUED,
        canonical_result_sha256=locked.result_sha256,
        source_sha256=locked.source_sha256,
        system_revision=locked.system_revision,
        system_configuration_fingerprint=locked.system_configuration_fingerprint,
        mapping_snapshot=locked.mapping_snapshot,
        fixed_parameter_snapshot=fixed,
        grid_type=normalized["grid_type"],
        grid_unit=normalized["grid_unit"],
        requested_grid=normalized["requested_grid"],
        study_configuration=normalized,
        public_api_identifier=snapshot["public_api_identifier"],
        scientific_status=(
            "SENSITIVITY_STUDY"
            if normalized["study_type"] == StudyType.TAU_MULTISCALE
            else "DIAGNOSTIC_EXPERIMENTAL"
        ),
        agencitylab_version=context["agencitylab_version"],
        studio_version=context["studio_version"],
        python_version=context["python_version"],
        execution_fingerprint=_fingerprint(payload),
        created_by=actor,
        queued_at=timezone.now(),
    )
    _record(
        study,
        event="SENSITIVITY_STUDY_QUEUED",
        detail=_("Queued sensitivity study %(number)s for canonical Run %(canonical)s.")
        % {"number": study.study_number, "canonical": locked.run_number},
    )
    transaction.on_commit(lambda: _enqueue(study.pk))
    return study


@transaction.atomic
def rerun_sensitivity_study(*, actor, study: SensitivityStudy) -> SensitivityStudy:
    source = SensitivityStudy.objects.select_related("analysis_run").get(pk=study.pk)
    return queue_sensitivity_study(
        actor=actor,
        run=source.analysis_run,
        configuration=source.study_configuration,
    )


@transaction.atomic
def cancel_sensitivity_study(*, actor, study: SensitivityStudy) -> SensitivityStudy:
    locked = SensitivityStudy.objects.select_for_update().select_related("analysis_run__analysis").get(pk=study.pk)
    if not can_run_analysis(actor, locked.analysis_run.analysis):
        raise PermissionDenied
    if locked.status != StudyStatus.QUEUED:
        raise ValidationError(_("Only queued sensitivity studies can be cancelled safely."))
    locked.status = StudyStatus.CANCELLED
    locked.completed_at = timezone.now()
    locked.save(update_fields=("status", "completed_at"))
    return locked


def get_sensitivity_study_or_404(*, user, study_id) -> SensitivityStudy:
    try:
        study = SensitivityStudy.objects.select_related(
            "analysis_run",
            "analysis_run__analysis",
            "analysis_run__analysis__project",
            "analysis_run__analysis__project__workspace",
            "system_revision__system",
        ).get(pk=study_id)
    except (SensitivityStudy.DoesNotExist, ValueError) as exc:
        raise Http404 from exc
    if not can_view_analysis_result(user, study.analysis_run):
        raise Http404
    return study
