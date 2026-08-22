import hashlib
import io
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from openpyxl import Workbook

from common.storage import LocalStorage
from datasets.models import (
    Dataset,
    DatasetColumnRole,
    DatasetImportStatus,
    DatasetSourceFormat,
)
from datasets.services import (
    add_dataset_version_from_upload,
    confirm_dataset_version,
    create_dataset_from_paste,
    create_dataset_from_upload,
    preview_page,
    update_column_annotations,
)
from datasets.tasks import inspect_dataset_version
from projects.services import create_project, delete_project
from workspaces.models import WorkspaceMembership, WorkspaceRole
from workspaces.permissions import (
    can_create_dataset,
    can_delete_dataset,
    can_view_dataset,
)
from workspaces.services import create_organisation_workspace

User = get_user_model()
PASSWORD = "Scientific-Plan4-Password!42"


def make_user(email: str, **extra):
    return User.objects.create_user(email=email, password=PASSWORD, **extra)


def make_project(owner, workspace, name="Data study"):
    return create_project(
        actor=owner,
        workspace=workspace,
        name=name,
        description="Dataset test project",
        domain="signal processing",
    )


def csv_upload(content: bytes, name="signal.csv"):
    return SimpleUploadedFile(name, content, content_type="text/csv")


def inspect(version):
    assert inspect_dataset_version(str(version.pk), version.inspection_generation) == "ready"
    version.refresh_from_db()
    return version


@pytest.mark.django_db
def test_local_storage_is_confined_immutable_and_hashes_exact_bytes(tmp_path):
    storage = LocalStorage(tmp_path)
    source = b"time,value\n0,1\n1,2\n"
    path, size, digest = storage.save_chunks("datasets/example/source.csv", (source[:5], source[5:]))

    assert path == "datasets/example/source.csv"
    assert size == len(source)
    assert digest == hashlib.sha256(source).hexdigest()
    assert storage.open(path, "rb").read() == source
    with pytest.raises(FileExistsError):
        storage.save(path, b"replacement")
    assert storage.open(path, "rb").read() == source
    with pytest.raises(ValueError):
        storage.save("../escape.csv", source)


@pytest.mark.django_db
def test_csv_source_hash_version_and_confirmation_are_explicit(tmp_path):
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Data Lab")
    project = make_project(owner, workspace)
    source = b"time,value\n0.00,1.0\n0.01,2.0\n0.02,3.0\n"

    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        dataset, version = create_dataset_from_upload(
            actor=owner,
            project=project,
            name="Rotor signal",
            description="Raw acquisition",
            uploaded_file=csv_upload(source),
        )
        assert isinstance(dataset.pk, uuid.UUID)
        assert isinstance(version.pk, uuid.UUID)
        assert version.source_sha256 == hashlib.sha256(source).hexdigest()
        assert version.version_number == 1
        assert dataset.current_version_id is None
        version = inspect(version)
        assert version.import_status == DatasetImportStatus.READY
        assert version.row_count == 3
        assert version.column_count == 2
        confirm_dataset_version(actor=owner, version=version)
        dataset.refresh_from_db()
        assert dataset.current_version_id == version.pk
        assert LocalStorage(tmp_path).open(version.source_path, "rb").read() == source


@pytest.mark.django_db
def test_new_version_preserves_previous_source_and_rejects_identical_hash(tmp_path):
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Version Lab")
    project = make_project(owner, workspace)
    first_bytes = b"time,value\n0,1\n1,2\n"
    second_bytes = b"time,value\n0,10\n1,20\n"

    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        dataset, first = create_dataset_from_upload(
            actor=owner,
            project=project,
            name="Versioned signal",
            description="",
            uploaded_file=csv_upload(first_bytes),
        )
        first = inspect(first)
        confirm_dataset_version(actor=owner, version=first)
        second = add_dataset_version_from_upload(
            actor=owner,
            dataset=dataset,
            uploaded_file=csv_upload(second_bytes, "signal-v2.csv"),
        )
        second = inspect(second)
        dataset.refresh_from_db()
        assert dataset.current_version_id == first.pk
        assert second.version_number == 2
        assert LocalStorage(tmp_path).open(first.source_path, "rb").read() == first_bytes
        assert LocalStorage(tmp_path).open(second.source_path, "rb").read() == second_bytes
        with pytest.raises(ValidationError, match="exact source bytes"):
            add_dataset_version_from_upload(
                actor=owner,
                dataset=dataset,
                uploaded_file=csv_upload(second_bytes, "again.csv"),
            )
        assert LocalStorage(tmp_path).open(first.source_path, "rb").read() == first_bytes


@pytest.mark.django_db
def test_paste_source_is_preserved_and_inspected(tmp_path):
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Paste Lab")
    project = make_project(owner, workspace)
    text = "time\tvalue\n0\t1\n1\t2\n"

    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        dataset, version = create_dataset_from_paste(
            actor=owner,
            project=project,
            name="Pasted table",
            description="",
            source_text=text,
            import_options={"delimiter": "\t", "has_header": True},
        )
        version = inspect(version)
        assert version.source_kind == "PASTE"
        assert version.row_count == 2
        assert LocalStorage(tmp_path).open(version.source_path, "rb").read() == text.encode()
        assert dataset.current_version_id is None


@pytest.mark.django_db
def test_tsv_and_custom_txt_import_options_are_persisted(tmp_path):
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Delimited Lab")
    project = make_project(owner, workspace)

    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        _, tsv = create_dataset_from_upload(
            actor=owner,
            project=project,
            name="TSV",
            description="",
            uploaded_file=csv_upload(b"time\tvalue\n0\t1\n1\t2\n", "table.tsv"),
        )
        tsv = inspect(tsv)
        assert tsv.source_format == DatasetSourceFormat.TSV
        assert tsv.import_options["delimiter"] == "\t"

        _, txt = create_dataset_from_upload(
            actor=owner,
            project=project,
            name="TXT",
            description="",
            uploaded_file=csv_upload(b"time;value\n0;1\n1;2\n", "table.txt"),
            import_options={"delimiter": ";", "has_header": True},
        )
        txt = inspect(txt)
        assert txt.source_format == DatasetSourceFormat.TXT
        assert txt.import_options["delimiter"] == ";"
        assert txt.row_count == 2


@pytest.mark.django_db
def test_xlsx_supports_sheet_selection_without_executing_formulas(tmp_path):
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Workbook Lab")
    project = make_project(owner, workspace)
    workbook = Workbook()
    first = workbook.active
    first.title = "Overview"
    first.append(["ignore"])
    data = workbook.create_sheet("Data")
    data.append(["time", "value"])
    data.append([0, 1])
    data.append([1, "=1+1"])
    payload = io.BytesIO()
    workbook.save(payload)

    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        _, version = create_dataset_from_upload(
            actor=owner,
            project=project,
            name="Workbook",
            description="",
            uploaded_file=SimpleUploadedFile(
                "workbook.xlsx",
                payload.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            import_options={"sheet": "Data", "has_header": True},
        )
        version = inspect(version)
        assert version.source_format == DatasetSourceFormat.XLSX
        assert version.import_options["sheet"] == "Data"
        assert version.row_count == 2
        assert any(issue["code"] == "FORMULA_CELLS" for issue in version.quality_issues)
        _, rows, _ = preview_page(version=version, page=1, page_size=10)
        assert rows[1][1] == "=1+1"


@pytest.mark.django_db
def test_column_annotations_detect_time_quality_and_observable_issues(tmp_path):
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Quality Lab")
    project = make_project(owner, workspace)
    source = b"time,value\n0.00,1\n0.01,\n0.01,ERROR\n0.04,inf\n0.03,5\n"

    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        _, version = create_dataset_from_upload(
            actor=owner,
            project=project,
            name="Quality signal",
            description="",
            uploaded_file=csv_upload(source),
        )
        version = inspect(version)
        update_column_annotations(
            actor=owner,
            version=version,
            annotations={
                1: {"role": DatasetColumnRole.TIME, "unit": "s"},
                2: {"role": DatasetColumnRole.OBSERVABLE, "unit": "m/s"},
            },
        )
        version.refresh_from_db()
        version = inspect(version)
        codes = {issue["code"] for issue in version.quality_issues}
        assert {"MISSING_VALUES", "INFINITE_VALUES", "NON_NUMERIC_VALUES"} <= codes
        assert {"TIME_DUPLICATE", "TIME_NON_MONOTONIC", "IRREGULAR_SAMPLING"} <= codes
        assert version.inspection_summary["time"]["median_dt"] is not None
        assert "observed_sampling_frequency_hz" in version.inspection_summary["time"]
        assert "tau" not in version.inspection_summary
        assert "w" not in version.inspection_summary


@pytest.mark.django_db
def test_dataset_permissions_inherit_workspace_roles_without_staff_bypass(tmp_path):
    owner = make_user("owner@example.com")
    editor = make_user("editor@example.com")
    analyst = make_user("analyst@example.com")
    viewer = make_user("viewer@example.com")
    outsider = make_user("outsider@example.com", is_staff=True)
    workspace = create_organisation_workspace(owner=owner, name="Permission Data Lab")
    WorkspaceMembership.objects.create(user=editor, workspace=workspace, role=WorkspaceRole.EDITOR)
    WorkspaceMembership.objects.create(user=analyst, workspace=workspace, role=WorkspaceRole.ANALYST)
    WorkspaceMembership.objects.create(user=viewer, workspace=workspace, role=WorkspaceRole.VIEWER)
    project = make_project(owner, workspace)

    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        dataset, _ = create_dataset_from_upload(
            actor=owner,
            project=project,
            name="Protected data",
            description="",
            uploaded_file=csv_upload(b"time,value\n0,1\n"),
        )
    assert can_create_dataset(owner, project)
    assert can_create_dataset(editor, project)
    assert can_view_dataset(analyst, dataset)
    assert can_view_dataset(viewer, dataset)
    assert not can_create_dataset(analyst, project)
    assert not can_create_dataset(viewer, project)
    assert can_delete_dataset(owner, dataset)
    assert not can_delete_dataset(editor, dataset)
    assert not can_view_dataset(outsider, dataset)


@pytest.mark.django_db
def test_private_dataset_metadata_preview_and_download_do_not_leak_across_workspaces(client, tmp_path):
    owner = make_user("owner@example.com")
    outsider = make_user("outsider@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Private Data Lab")
    project = make_project(owner, workspace)
    source = b"time,value\n0,1\n1,2\n"

    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        dataset, version = create_dataset_from_upload(
            actor=owner,
            project=project,
            name="Private dataset",
            description="",
            uploaded_file=csv_upload(source),
        )
        version = inspect(version)
        detail = reverse(
            "datasets:overview",
            args=(workspace.slug, project.pk, project.slug, dataset.pk, dataset.slug),
        )
        download = reverse(
            "datasets:download",
            args=(workspace.slug, project.pk, project.slug, dataset.pk, dataset.slug, version.pk),
        )
        client.force_login(outsider)
        assert client.get(detail).status_code == 404
        assert client.get(download).status_code == 404
        client.force_login(owner)
        response = client.get(download)
        assert response.status_code == 200
        assert response["Content-Disposition"].startswith("attachment;")
        assert b"".join(response.streaming_content) == source


@pytest.mark.django_db
def test_viewer_cannot_mutate_columns_or_import_but_can_preview(client, tmp_path):
    owner = make_user("owner@example.com")
    viewer = make_user("viewer@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Read Lab")
    WorkspaceMembership.objects.create(user=viewer, workspace=workspace, role=WorkspaceRole.VIEWER)
    project = make_project(owner, workspace)
    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        dataset, version = create_dataset_from_upload(
            actor=owner,
            project=project,
            name="Read only",
            description="",
            uploaded_file=csv_upload(b"time,value\n0,1\n1,2\n"),
        )
        version = inspect(version)
        client.force_login(viewer)
        import_url = reverse("datasets:import", args=(workspace.slug, project.pk, project.slug))
        columns_url = reverse(
            "datasets:columns",
            args=(workspace.slug, project.pk, project.slug, dataset.pk, dataset.slug),
        ) + f"?version={version.pk}"
        preview_url = reverse(
            "datasets:preview",
            args=(workspace.slug, project.pk, project.slug, dataset.pk, dataset.slug),
        ) + f"?version={version.pk}"
        assert client.get(import_url).status_code == 403
        assert client.post(columns_url, {"role_1": "TIME", "unit_1": "s"}).status_code == 403
        assert client.get(preview_url).status_code == 200


@pytest.mark.django_db
def test_current_version_cannot_point_to_another_dataset(tmp_path):
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Invariant Lab")
    project = make_project(owner, workspace)
    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        first, _ = create_dataset_from_upload(
            actor=owner,
            project=project,
            name="First",
            description="",
            uploaded_file=csv_upload(b"x\n1\n"),
        )
        second, second_version = create_dataset_from_upload(
            actor=owner,
            project=project,
            name="Second",
            description="",
            uploaded_file=csv_upload(b"x\n2\n"),
        )
        first.current_version = second_version
        with pytest.raises(ValidationError, match="another dataset"):
            first.full_clean()
        assert second.pk != first.pk


@pytest.mark.django_db
def test_project_hard_delete_is_blocked_when_dataset_exists(tmp_path):
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Retention Lab")
    project = make_project(owner, workspace)
    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        create_dataset_from_upload(
            actor=owner,
            project=project,
            name="Retained data",
            description="",
            uploaded_file=csv_upload(b"x\n1\n"),
        )
    with pytest.raises(ValidationError, match="contains datasets"):
        delete_project(actor=owner, project=project)
    assert Dataset.objects.filter(project=project).exists()


@pytest.mark.django_db
def test_upload_size_limit_and_unsupported_format_fail_cleanly(tmp_path):
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Limits Lab")
    project = make_project(owner, workspace)
    with override_settings(DATASET_STORAGE_ROOT=tmp_path, DATASET_MAX_UPLOAD_BYTES=4):
        with pytest.raises(ValidationError, match="size limit"):
            create_dataset_from_upload(
                actor=owner,
                project=project,
                name="Too big",
                description="",
                uploaded_file=csv_upload(b"12345"),
            )
    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        with pytest.raises(ValidationError, match="Unsupported dataset format"):
            create_dataset_from_upload(
                actor=owner,
                project=project,
                name="Legacy",
                description="",
                uploaded_file=SimpleUploadedFile("legacy.xls", b"not-xls"),
            )


@pytest.mark.django_db
def test_malformed_source_becomes_failed_without_raw_parser_error(tmp_path):
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Failure Lab")
    project = make_project(owner, workspace)
    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        _, version = create_dataset_from_upload(
            actor=owner,
            project=project,
            name="Broken workbook",
            description="",
            uploaded_file=SimpleUploadedFile("broken.xlsx", b"this is not a zip workbook"),
        )
        assert inspect_dataset_version(str(version.pk), version.inspection_generation) == "failed"
        version.refresh_from_db()
        assert version.import_status == DatasetImportStatus.FAILED
        assert "workbook could not be read" in version.failure_summary.lower()
        assert "BadZipFile" not in version.failure_summary


@pytest.mark.django_db
def test_decimal_comma_does_not_silently_define_physical_parameters(tmp_path):
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Decimal Lab")
    project = make_project(owner, workspace)
    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        _, version = create_dataset_from_upload(
            actor=owner,
            project=project,
            name="Decimal comma",
            description="",
            uploaded_file=csv_upload(b"time;value\n0,0;1,2\n0,1;2,3\n", "decimal.txt"),
            import_options={
                "delimiter": ";",
                "decimal_separator": ",",
                "has_header": True,
            },
        )
        version = inspect(version)
        assert version.columns.get(position=2).summary["minimum"] == pytest.approx(1.2)
        assert all(key not in version.inspection_summary for key in ("A_ref", "tau", "w", "P_c"))
