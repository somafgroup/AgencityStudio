from types import SimpleNamespace

import numpy as np
import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import override_settings
from django.urls import reverse

from analyses.models import (
    Analysis,
    AnalysisResultArtifact,
    RunErrorCategory,
    RunStatus,
    SourceType,
)
from analyses.services import configure_analysis, create_analysis, queue_analysis_run
from analyses.tasks import execute_analysis_run
from analyses.validation import PreflightError, validate_sample_contract, validate_units
from labbridge.execution import CanonicalLabError, execute_canonical_analysis
from projects.services import delete_project
from systems.models import MemoryWindowMode, SystemRevision
from tests.test_analyses import _project_and_system, _raw_source, _user
from workspaces.models import WorkspaceMembership, WorkspaceRole


def _signal():
    xi = np.arange(20, dtype=float) * 0.1
    return xi, np.sin(2.0 * np.pi * xi)


def test_unspecified_w_preflight_does_not_substitute_tau_but_lab_remains_authoritative():
    xi, u = _signal()
    validate_sample_contract(xi, u, requested_w=None, tau=0.25)

    with pytest.raises(CanonicalLabError, match="integer multiple"):
        execute_canonical_analysis(
            u=u,
            xi=xi,
            A_ref=1.5,
            tau=0.25,
            w=None,
            P_c=12.0,
            unit="rad",
            coordinate_unit="s",
            power_unit="W",
        )


def test_explicit_w_preflight_rejects_incompatible_sampling_without_modifying_w():
    xi, u = _signal()
    with pytest.raises(PreflightError, match="integer multiple"):
        validate_sample_contract(xi, u, requested_w=0.25, tau=0.2)


@pytest.mark.parametrize(
    ("xi", "u", "message"),
    [
        (np.array([0.0, 0.2, 0.1]), np.array([0.0, 1.0, 2.0]), "strictly increasing"),
        (np.array([0.0, 0.1, 0.21]), np.array([0.0, 1.0, 2.0]), "irregularly sampled"),
        (np.array([0.0, 0.1, 0.2]), np.array([0.0, np.nan, 2.0]), "finite"),
    ],
)
def test_preflight_rejects_bad_source_without_sort_fill_or_resample(xi, u, message):
    with pytest.raises(PreflightError, match=message):
        validate_sample_contract(xi, u, requested_w=0.1, tau=0.2)


def test_execution_requires_exact_unit_representation_instead_of_silent_conversion():
    revision = SimpleNamespace(
        a_ref_unit="m/s",
        tau_unit="s",
        w_mode=MemoryWindowMode.UNSPECIFIED,
        w_unit="",
    )
    system_observable = SimpleNamespace(unit="m/s")
    coordinate = {"unit": "ms"}
    observable = {"unit": "m/s"}

    with pytest.raises(PreflightError, match="No unit conversion occurs"):
        validate_units(
            coordinate=coordinate,
            observable=observable,
            revision=revision,
            system_observable=system_observable,
        )


@pytest.mark.django_db(transaction=True)
def test_unspecified_w_lab_rejection_marks_run_failed_without_result(tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner = _user("lab-authority@example.com")
        _workspace, project, revision, observable = _project_and_system(owner)
        version = _raw_source(owner, project)
        SystemRevision.objects.filter(pk=revision.pk).update(tau_value=0.25, tau_value_text="0.25")
        revision.refresh_from_db()
        monkeypatch.setattr("analyses.services._enqueue", lambda _run_id: None)

        analysis = create_analysis(
            actor=owner,
            project=project,
            name="Lab authority failure",
            source_type=SourceType.RAW_DATASET_VERSION,
            source_id=str(version.pk),
        )
        configure_analysis(
            actor=owner,
            analysis=analysis,
            coordinate_position=1,
            observable_position=2,
            system_revision=revision,
            system_observable=observable,
        )
        run = queue_analysis_run(actor=owner, analysis=analysis)
        assert run.parameter_snapshot["w"]["requested_value"] is None

        assert execute_analysis_run(str(run.pk)) == "failed"
        run.refresh_from_db()
        assert run.status == RunStatus.FAILED
        assert run.error_category == RunErrorCategory.LAB_VALIDATION_ERROR
        assert "AgencityLab rejected this configuration" in run.error_message
        assert not AnalysisResultArtifact.objects.filter(run=run).exists()

        run.result_sha256 = "0" * 64
        with pytest.raises(ValidationError, match="immutable"):
            run.save()


@pytest.mark.django_db
def test_project_with_analysis_is_protected_from_hard_delete():
    owner = _user("project-protection@example.com")
    _workspace, project, _revision, _observable = _project_and_system(owner)
    Analysis.objects.create(project=project, name="Pinned analysis", created_by=owner)

    with pytest.raises(ValidationError, match="contains analyses"):
        delete_project(actor=owner, project=project)


@pytest.mark.django_db(transaction=True)
def test_analysis_run_isolation_and_viewer_mutation_policy(client, tmp_path, monkeypatch):
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, ANALYSIS_MAX_ROWS=1000):
        owner = _user("isolation-owner@example.com")
        workspace, project, revision, observable = _project_and_system(owner)
        version = _raw_source(owner, project)
        viewer = _user("isolation-viewer@example.com")
        analyst = _user("isolation-analyst@example.com")
        outsider = _user("isolation-outsider@example.com")
        WorkspaceMembership.objects.create(workspace=workspace, user=viewer, role=WorkspaceRole.VIEWER)
        WorkspaceMembership.objects.create(workspace=workspace, user=analyst, role=WorkspaceRole.ANALYST)
        monkeypatch.setattr("analyses.services._enqueue", lambda _run_id: None)

        analysis = create_analysis(
            actor=owner,
            project=project,
            name="Isolation run",
            source_type=SourceType.RAW_DATASET_VERSION,
            source_id=str(version.pk),
        )
        configure_analysis(
            actor=owner,
            analysis=analysis,
            coordinate_position=1,
            observable_position=2,
            system_revision=revision,
            system_observable=observable,
        )
        run = queue_analysis_run(actor=owner, analysis=analysis)
        assert execute_analysis_run(str(run.pk)) == "completed"
        run.refresh_from_db()

        client.force_login(outsider)
        assert client.get(reverse("analysis:detail", args=[analysis.pk])).status_code == 404
        assert client.get(reverse("analysis:run-detail", args=[analysis.pk, run.pk])).status_code == 404
        assert client.post(reverse("analysis:run-rerun", args=[analysis.pk, run.pk])).status_code == 404

        client.force_login(viewer)
        assert client.get(reverse("analysis:run-detail", args=[analysis.pk, run.pk])).status_code == 200
        assert client.post(reverse("analysis:run-rerun", args=[analysis.pk, run.pk])).status_code == 403

        client.force_login(analyst)
        assert client.post(reverse("analysis:delete", args=[analysis.pk])).status_code == 403

        with pytest.raises(PermissionDenied):
            create_analysis(
                actor=viewer,
                project=project,
                name="Forbidden",
                source_type=SourceType.RAW_DATASET_VERSION,
                source_id=str(version.pk),
            )
