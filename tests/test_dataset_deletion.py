import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from datasets.services import create_dataset_from_upload, delete_dataset
from datasets.storage import dataset_storage
from projects.services import create_project
from workspaces.models import WorkspaceMembership, WorkspaceRole
from workspaces.services import create_organisation_workspace

User = get_user_model()
PASSWORD = "Scientific-Plan4-Deletion!42"


@pytest.mark.django_db(transaction=True)
def test_owner_dataset_delete_removes_metadata_and_private_source_after_commit(tmp_path):
    owner = User.objects.create_user(email="delete-owner@example.com", password=PASSWORD)
    workspace = create_organisation_workspace(owner=owner, name="Deletion Workspace")
    project = create_project(actor=owner, workspace=workspace, name="Deletion Project")

    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        dataset, version = create_dataset_from_upload(
            actor=owner,
            project=project,
            name="Disposable Dataset",
            description="",
            uploaded_file=SimpleUploadedFile("source.csv", b"time,value\n0,1\n"),
        )
        source_path = version.source_path
        assert dataset_storage().exists(source_path)

        delete_dataset(actor=owner, dataset=dataset)

        assert not dataset_storage().exists(source_path)
        assert not project.datasets.filter(pk=dataset.pk).exists()


@pytest.mark.django_db
def test_editor_cannot_delete_dataset(tmp_path):
    owner = User.objects.create_user(email="delete-owner-2@example.com", password=PASSWORD)
    editor = User.objects.create_user(email="delete-editor@example.com", password=PASSWORD)
    workspace = create_organisation_workspace(owner=owner, name="Deletion Permission Workspace")
    WorkspaceMembership.objects.create(user=editor, workspace=workspace, role=WorkspaceRole.EDITOR)
    project = create_project(actor=owner, workspace=workspace, name="Deletion Permission Project")

    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        dataset, version = create_dataset_from_upload(
            actor=owner,
            project=project,
            name="Owner-only Delete",
            description="",
            uploaded_file=SimpleUploadedFile("source.csv", b"time,value\n0,1\n"),
        )
        source_path = version.source_path
        with pytest.raises(PermissionDenied):
            delete_dataset(actor=editor, dataset=dataset)

        assert dataset_storage().exists(source_path)
        assert project.datasets.filter(pk=dataset.pk).exists()
