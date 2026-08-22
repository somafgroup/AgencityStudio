import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from datasets.models import Dataset
from datasets.services import create_dataset_from_upload
from projects.models import Project
from projects.services import create_project
from workspaces.services import create_organisation_workspace

User = get_user_model()
PASSWORD = "Scientific-Plan4-Retention!42"


@pytest.mark.django_db
def test_project_delete_endpoint_reports_retained_dataset_without_deleting(client, tmp_path):
    owner = User.objects.create_user(email="retention-owner@example.com", password=PASSWORD)
    workspace = create_organisation_workspace(owner=owner, name="Retention Workspace")
    project = create_project(actor=owner, workspace=workspace, name="Protected Project")
    with override_settings(DATASET_STORAGE_ROOT=tmp_path):
        dataset, _version = create_dataset_from_upload(
            actor=owner,
            project=project,
            name="Protected Dataset",
            description="",
            uploaded_file=SimpleUploadedFile("source.csv", b"time,value\n0,1\n"),
        )
        client.force_login(owner)
        response = client.post(
            reverse(
                "projects:delete",
                args=(workspace.slug, project.pk, project.slug),
            ),
            {"confirmation": project.name},
        )

    assert response.status_code == 200
    assert b"contains datasets" in response.content
    assert Project.objects.filter(pk=project.pk).exists()
    assert Dataset.objects.filter(pk=dataset.pk).exists()
