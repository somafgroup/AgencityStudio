"""Celery execution for immutable AgencityStudio sensitivity studies."""

from __future__ import annotations

import logging
import time
import uuid

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from analyses.models import AnalysisRun
from analyses.sources import SourceContractError, descriptor_for, materialize_vectors
from analyses.storage import analysis_storage
from labbridge.sensitivity import (
    SensitivityLabError,
    execute_tau_multiscale,
    execute_window_sensitivity,
)
from projects.models import ProjectActivity

from .models import (
    SensitivityErrorCategory,
    SensitivityResultArtifact,
    SensitivityStudy,
    StudyStatus,
    StudyType,
)
from .storage import write_sensitivity_result

logger = logging.getLogger(__name__)


def _locked(study_id) -> SensitivityStudy:
    return (
        SensitivityStudy.objects.select_for_update()
        .select_related(
            "analysis_run",
            "analysis_run__analysis",
            "analysis_run__analysis__project",
            "system_revision",
        )
        .get(pk=study_id)
    )


def _record(study: SensitivityStudy, event: str, detail: str) -> None:
    ProjectActivity.objects.create(
        project=study.analysis_run.analysis.project,
        actor=study.created_by,
        event=event,
        detail=detail[:255],
    )


def _fail(study_id, category: str, message: str) -> str:
    with transaction.atomic():
        try:
            study = _locked(study_id)
        except SensitivityStudy.DoesNotExist:
            return "missing-after-failure"
        if study.status != StudyStatus.RUNNING:
            return "stale-failure"
        study.status = StudyStatus.FAILED
        study.error_category = category
        study.error_message = str(message)[:500]
        study.completed_at = timezone.now()
        study.save(update_fields=("status", "error_category", "error_message", "completed_at"))
        _record(
            study,
            "SENSITIVITY_STUDY_FAILED",
            _("Sensitivity study %(number)s failed.") % {"number": study.study_number},
        )
    return "failed"


def _vectors(run: AnalysisRun):
    time_mapping = run.mapping_snapshot["time"]
    observable_mapping = run.mapping_snapshot["observable"]
    descriptor = descriptor_for(
        dataset_version=run.source_dataset_version,
        prepared_artifact=run.source_prepared_artifact,
    )
    if descriptor.sha256 != run.source_sha256:
        raise SourceContractError("The pinned source SHA-256 no longer matches the canonical Run.")
    return materialize_vectors(
        dataset_version=run.source_dataset_version,
        prepared_artifact=run.source_prepared_artifact,
        coordinate_position=int(time_mapping["position"]),
        observable_position=int(observable_mapping["position"]),
    )


@shared_task(name="sensitivity.execute_sensitivity_study")
def execute_sensitivity_study(study_id: str) -> str:
    """Execute one frozen sensitivity contract once and publish one complete artifact."""
    started_clock = time.monotonic()
    with transaction.atomic():
        try:
            study = _locked(study_id)
        except SensitivityStudy.DoesNotExist:
            return "missing"
        if study.status == StudyStatus.RUNNING:
            return "already-running"
        if study.status in {StudyStatus.COMPLETED, StudyStatus.FAILED, StudyStatus.CANCELLED}:
            return "already-finished"
        if study.status != StudyStatus.QUEUED:
            return "not-queued"
        study.status = StudyStatus.RUNNING
        study.started_at = timezone.now()
        study.error_category = ""
        study.error_message = ""
        study.save(update_fields=("status", "started_at", "error_category", "error_message"))

    logger.info(
        "sensitivity.study_started study_id=%s type=%s candidates=%s lab_version=%s",
        study_id,
        study.study_type,
        len(study.requested_grid),
        study.agencitylab_version,
    )
    saved_path = None
    try:
        run = study.analysis_run
        if run.result_sha256 != study.canonical_result_sha256:
            return _fail(
                study_id,
                SensitivityErrorCategory.RESULT_INPUT_ERROR,
                _("The canonical result SHA-256 no longer matches the sensitivity-study provenance."),
            )
        if run.source_sha256 != study.source_sha256:
            return _fail(
                study_id,
                SensitivityErrorCategory.RESULT_INPUT_ERROR,
                _("The source SHA-256 no longer matches the sensitivity-study provenance."),
            )
        xi, u = _vectors(run)
        params = study.fixed_parameter_snapshot
        A_ref = float(params["A_ref"]["value"])
        P_c = float(params["P_c"]["value"])
        base_tau = float(params["base_tau"]["value"])
        base_w = params["base_w"]

        if study.study_type == StudyType.TAU_MULTISCALE:
            execution = execute_tau_multiscale(
                u=u,
                xi=xi,
                taus=[float(value) for value in study.requested_grid],
                A_ref=A_ref,
                P_c=P_c,
                requested_w_mode=str(base_w.get("mode") or "UNSPECIFIED"),
                requested_w=base_w.get("requested_value"),
            )
        elif study.study_type == StudyType.W_SENSITIVITY:
            execution = execute_window_sensitivity(
                u=u,
                xi=xi,
                tau=base_tau,
                A_ref=A_ref,
                P_c=P_c,
                candidates=[float(value) for value in study.requested_grid],
            )
        else:
            return _fail(
                study_id,
                SensitivityErrorCategory.STUDIO_INTERNAL_ERROR,
                _("Unsupported sensitivity study type."),
            )

        artifact_id = uuid.uuid4()
        saved_path, serialized = write_sensitivity_result(
            result=execution.result,
            study=study,
            artifact_id=artifact_id,
        )
        with transaction.atomic():
            locked = _locked(study_id)
            if locked.status != StudyStatus.RUNNING:
                analysis_storage().delete(saved_path)
                return "stale-result"
            if locked.analysis_run.result_sha256 != locked.canonical_result_sha256:
                analysis_storage().delete(saved_path)
                return _fail(
                    study_id,
                    SensitivityErrorCategory.RESULT_INPUT_ERROR,
                    _("The canonical result changed while the sensitivity study was running."),
                )
            SensitivityResultArtifact.objects.create(
                id=artifact_id,
                study=locked,
                storage_path=saved_path,
                format=serialized.manifest["format"],
                schema_version=serialized.manifest["schema_version"],
                sha256=serialized.sha256,
                size_bytes=serialized.size_bytes,
                manifest=serialized.manifest,
            )
            locked.status = StudyStatus.COMPLETED
            locked.result_sha256 = serialized.sha256
            locked.warnings = [*locked.warnings, *execution.warnings]
            locked.scientific_status = execution.scientific_status
            locked.completed_at = timezone.now()
            locked.save(
                update_fields=(
                    "status",
                    "result_sha256",
                    "warnings",
                    "scientific_status",
                    "completed_at",
                )
            )
            _record(
                locked,
                "SENSITIVITY_STUDY_COMPLETED",
                _("Sensitivity study %(number)s completed.") % {"number": locked.study_number},
            )
        logger.info(
            "sensitivity.study_completed study_id=%s type=%s candidates=%s duration_ms=%s lab_version=%s",
            study_id,
            study.study_type,
            len(study.requested_grid),
            round((time.monotonic() - started_clock) * 1000),
            study.agencitylab_version,
        )
        return "completed"
    except SensitivityLabError as exc:
        if saved_path:
            analysis_storage().delete(saved_path)
        return _fail(
            study_id,
            exc.category,
            _("AgencityLab rejected this sensitivity configuration: %(message)s")
            % {"message": str(exc)},
        )
    except SourceContractError as exc:
        if saved_path:
            analysis_storage().delete(saved_path)
        return _fail(study_id, SensitivityErrorCategory.RESULT_INPUT_ERROR, str(exc))
    except OSError:
        if saved_path:
            try:
                analysis_storage().delete(saved_path)
            except OSError:
                logger.exception("sensitivity.result_cleanup_failed study_id=%s", study_id)
        return _fail(
            study_id,
            SensitivityErrorCategory.STORAGE_ERROR,
            _("The sensitivity result could not be stored safely."),
        )
    except Exception:
        if saved_path:
            try:
                analysis_storage().delete(saved_path)
            except OSError:
                logger.exception("sensitivity.result_cleanup_failed study_id=%s", study_id)
        logger.exception("sensitivity.study_failed_unexpected study_id=%s", study_id)
        return _fail(
            study_id,
            SensitivityErrorCategory.STUDIO_INTERNAL_ERROR,
            _("The sensitivity study failed because of an internal Studio error."),
        )
