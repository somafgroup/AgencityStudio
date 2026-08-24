import hashlib

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.deletion import ProtectedError
from django.test import override_settings
from django.urls import reverse

from common.storage import LocalStorage
from datasets.models import DataPreparationStatus, DatasetColumnRole
from datasets.preparation import PreparationError, apply_recipe, load_source_table
from datasets.preparation_services import (
    add_preparation_step,
    create_preparation,
    duplicate_preparation,
    prepared_preview_page,
    rerun_preparation,
    run_preparation,
)
from datasets.preparation_tasks import execute_data_preparation
from datasets.services import create_dataset_from_upload, update_column_annotations
from datasets.tasks import inspect_dataset_version
from projects.services import create_project
from workspaces.models import WorkspaceMembership, WorkspaceRole
from workspaces.permissions import can_create_preparation, can_edit_dataset
from workspaces.services import create_organisation_workspace

User = get_user_model()
PASSWORD = "Scientific-Plan5-Password!42"


def make_user(email):
    return User.objects.create_user(email=email, password=PASSWORD)


def make_ready_dataset(owner, workspace, tmp_path, source=None):
    project = create_project(
        actor=owner,
        workspace=workspace,
        name="Preparation project",
        description="",
        domain="signal processing",
    )
    payload = source or b"time,velocity\n0,0\n1,3.6\n2,\n3,10.8\n4,14.4\n"
    dataset, version = create_dataset_from_upload(
        actor=owner,
        project=project,
        name="Raw signal",
        description="Immutable source",
        uploaded_file=SimpleUploadedFile("signal.csv", payload, content_type="text/csv"),
    )
    assert inspect_dataset_version(str(version.pk), version.inspection_generation) == "ready"
    version.refresh_from_db()
    update_column_annotations(
        actor=owner,
        version=version,
        annotations={
            1: {"role": DatasetColumnRole.TIME, "unit": "s"},
            2: {"role": DatasetColumnRole.OBSERVABLE, "unit": "km/h"},
        },
    )
    version.refresh_from_db()
    assert inspect_dataset_version(str(version.pk), version.inspection_generation) == "ready"
    version.refresh_from_db()
    return project, dataset, version, payload


def execute(preparation, monkeypatch):
    monkeypatch.setattr("datasets.preparation_services._enqueue_preparation", lambda _pk: None)
    run_preparation(actor=preparation.created_by, preparation=preparation)
    preparation.refresh_from_db()
    assert preparation.status == DataPreparationStatus.QUEUED
    assert execute_data_preparation(str(preparation.pk)) == "ready"
    preparation.refresh_from_db()
    return preparation


@pytest.mark.django_db
def test_explicit_recipe_materializes_immutable_provenance_without_touching_raw(tmp_path, monkeypatch):
    owner = make_user("prep-owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Preparation Lab")
    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        _project, dataset, version, raw_bytes = make_ready_dataset(owner, workspace, tmp_path)
        original_hash = version.source_sha256
        preparation = create_preparation(
            actor=owner,
            source_version=version,
            name="Clean velocity",
        )
        add_preparation_step(
            actor=owner,
            preparation=preparation,
            step={
                "operation": "time_crop",
                "parameters": {"time_column": 1, "start": 1, "end": 4},
            },
        )
        preparation.refresh_from_db()
        add_preparation_step(
            actor=owner,
            preparation=preparation,
            step={
                "operation": "missing_values",
                "parameters": {
                    "columns": [2],
                    "action": "interpolate_linear",
                    "coordinate_column": 1,
                },
            },
        )
        preparation.refresh_from_db()
        add_preparation_step(
            actor=owner,
            preparation=preparation,
            step={
                "operation": "unit_conversion",
                "parameters": {"column": 2, "target_unit": "m/s"},
            },
        )
        preparation.refresh_from_db()
        preparation = execute(preparation, monkeypatch)
        artifact = preparation.artifact

        assert preparation.source_version_id == version.pk
        assert [step["operation"] for step in preparation.recipe] == [
            "time_crop",
            "missing_values",
            "unit_conversion",
        ]
        assert len(preparation.recipe_hash) == 64
        assert len(artifact.prepared_sha256) == 64
        assert artifact.prepared_sha256 != original_hash
        assert artifact.row_count == 4
        assert artifact.column_metadata[1]["unit"] == "m/s"
        assert preparation.engine_id == "studio.tabular-preparation"
        assert preparation.studio_version
        assert "numpy" in preparation.dependency_versions
        assert "Pint" in preparation.dependency_versions
        assert LocalStorage(tmp_path).open(version.source_path, "rb").read() == raw_bytes
        version.refresh_from_db()
        assert version.source_sha256 == original_hash == hashlib.sha256(raw_bytes).hexdigest()
        assert dataset.pk == version.dataset_id


@pytest.mark.django_db
def test_crop_missing_resample_smoothing_and_unit_conversion_contracts(tmp_path):
    owner = make_user("engine@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Engine Lab")
    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        _project, _dataset, version, _raw = make_ready_dataset(owner, workspace, tmp_path)
        table = load_source_table(version)
        table, warnings = apply_recipe(
            table,
            [
                {"operation": "time_crop", "parameters": {"time_column": 1, "start": 0, "end": 4}},
                {
                    "operation": "missing_values",
                    "parameters": {"columns": [2], "action": "interpolate_linear", "coordinate_column": 1},
                },
                {
                    "operation": "resample",
                    "parameters": {"time_column": 1, "columns": [2], "target_dt": 0.5, "dt_unit": "s"},
                },
                {"operation": "moving_average", "parameters": {"columns": [2], "window_samples": 3}},
                {"operation": "unit_conversion", "parameters": {"column": 2, "target_unit": "m/s"}},
            ],
        )
        assert len(table.rows) == 9
        assert table.columns[1]["unit"] == "m/s"
        assert {item["code"] for item in warnings} >= {
            "TIME_CROP",
            "LINEAR_INTERPOLATION",
            "RESAMPLED",
            "MOVING_AVERAGE",
            "UNIT_CONVERTED",
        }
        assert all("tau" not in item["details"] and "w" not in item["details"] for item in warnings)


@pytest.mark.django_db
def test_interpolation_refuses_duplicate_coordinate_until_user_resolves_it(tmp_path):
    owner = make_user("duplicate-time@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Duplicate Time Lab")
    source = b"time,velocity\n0,1\n1,\n1,3\n2,4\n"
    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        _project, _dataset, version, _raw = make_ready_dataset(owner, workspace, tmp_path, source)
        table = load_source_table(version)
        with pytest.raises(PreparationError, match="strictly increasing"):
            apply_recipe(
                table,
                [
                    {
                        "operation": "missing_values",
                        "parameters": {
                            "columns": [2],
                            "action": "interpolate_linear",
                            "coordinate_column": 1,
                        },
                    }
                ],
            )


@pytest.mark.django_db
def test_analyst_can_prepare_derivatives_but_cannot_mutate_raw_dataset(tmp_path):
    owner = make_user("role-owner@example.com")
    analyst = make_user("analyst@example.com")
    viewer = make_user("viewer-prep@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Roles Lab")
    WorkspaceMembership.objects.create(user=analyst, workspace=workspace, role=WorkspaceRole.ANALYST)
    WorkspaceMembership.objects.create(user=viewer, workspace=workspace, role=WorkspaceRole.VIEWER)
    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        _project, dataset, version, _raw = make_ready_dataset(owner, workspace, tmp_path)
        assert can_create_preparation(analyst, dataset)
        assert not can_edit_dataset(analyst, dataset)
        preparation = create_preparation(actor=analyst, source_version=version, name="Analyst derivation")
        assert preparation.created_by == analyst
        assert not can_create_preparation(viewer, dataset)
        with pytest.raises(PermissionDenied):
            create_preparation(actor=viewer, source_version=version, name="Forbidden")


@pytest.mark.django_db
def test_preparation_isolation_and_download_do_not_leak_across_workspaces(client, tmp_path, monkeypatch):
    owner = make_user("private-prep@example.com")
    outsider = make_user("private-outsider@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Private Preparation Lab")
    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        project, dataset, version, _raw = make_ready_dataset(owner, workspace, tmp_path)
        preparation = create_preparation(actor=owner, source_version=version, name="Private derivation")
        add_preparation_step(
            actor=owner,
            preparation=preparation,
            step={"operation": "row_range", "parameters": {"start_row": 1, "end_row": 3}},
        )
        preparation.refresh_from_db()
        preparation = execute(preparation, monkeypatch)
        detail = reverse(
            "datasets:preparation-detail",
            args=(workspace.slug, project.pk, project.slug, dataset.pk, dataset.slug, preparation.pk),
        )
        download = reverse(
            "datasets:preparation-download",
            args=(workspace.slug, project.pk, project.slug, dataset.pk, dataset.slug, preparation.pk),
        )
        client.force_login(outsider)
        assert client.get(detail).status_code == 404
        assert client.get(download).status_code == 404
        client.force_login(owner)
        assert client.get(detail).status_code == 200
        response = client.get(download)
        assert response.status_code == 200
        assert response["Content-Disposition"].startswith("attachment;")


@pytest.mark.django_db
def test_source_version_deletion_is_protected_when_preparation_exists(tmp_path):
    owner = make_user("protect-source@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Protection Lab")
    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        _project, _dataset, version, _raw = make_ready_dataset(owner, workspace, tmp_path)
        create_preparation(actor=owner, source_version=version, name="Pinned lineage")
        with pytest.raises(ProtectedError):
            version.delete()


@pytest.mark.django_db
def test_duplicate_preparation_bounds_generated_name_to_model_limit(tmp_path):
    owner = make_user("duplicate-name@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Duplicate Name Lab")
    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        _project, _dataset, version, _raw = make_ready_dataset(owner, workspace, tmp_path)
        source = create_preparation(actor=owner, source_version=version, name="x" * 180)
        clone = duplicate_preparation(actor=owner, preparation=source)
        assert clone.pk != source.pk
        assert clone.name.startswith("Copy of ")
        assert len(clone.name) == 180
        assert clone.source_version_id == source.source_version_id


@pytest.mark.django_db
def test_rerun_same_source_and_recipe_is_deterministic(tmp_path, monkeypatch):
    owner = make_user("rerun@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Reproducibility Lab")
    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        _project, _dataset, version, _raw = make_ready_dataset(owner, workspace, tmp_path)
        preparation = create_preparation(actor=owner, source_version=version, name="Deterministic")
        add_preparation_step(
            actor=owner,
            preparation=preparation,
            step={"operation": "row_range", "parameters": {"start_row": 1, "end_row": 4}},
        )
        preparation.refresh_from_db()
        first = execute(preparation, monkeypatch)
        first_hash = first.artifact.prepared_sha256
        second = rerun_preparation(actor=owner, preparation=first)
        assert second.status == DataPreparationStatus.QUEUED
        assert execute_data_preparation(str(second.pk)) == "ready"
        second.refresh_from_db()
        assert second.source_version_id == first.source_version_id
        assert second.recipe == first.recipe
        assert second.recipe_hash == first.recipe_hash
        assert second.artifact.prepared_sha256 == first_hash


@pytest.mark.django_db
def test_prepared_preview_reads_materialized_result_not_raw_source(tmp_path, monkeypatch):
    owner = make_user("preview-prep@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Preview Lab")
    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        _project, _dataset, version, _raw = make_ready_dataset(owner, workspace, tmp_path)
        preparation = create_preparation(actor=owner, source_version=version, name="Cropped")
        add_preparation_step(
            actor=owner,
            preparation=preparation,
            step={"operation": "row_range", "parameters": {"start_row": 2, "end_row": 3}},
        )
        preparation.refresh_from_db()
        preparation = execute(preparation, monkeypatch)
        headers, rows, offset = prepared_preview_page(preparation=preparation, page=1, page_size=10)
        assert headers == ["time", "velocity"]
        assert len(rows) == 2
        assert offset == 0
