import pytest
from django.contrib.auth import get_user_model

from datasets.models import Dataset, DatasetImportStatus, DatasetSourceFormat, DatasetSourceKind, DatasetVersion
from datasets.tasks import inspect_dataset_version
from projects.models import ProjectActivity, ProjectActivityEvent
from projects.services import create_project
from workspaces.services import create_organisation_workspace

User = get_user_model()


@pytest.mark.django_db
def test_duplicate_delivery_does_not_reinspect_terminal_version():
    owner = User.objects.create_user(email="task-owner@example.com", password="Plan4-task-test-password!42")
    workspace = create_organisation_workspace(owner=owner, name="Task Idempotence Lab")
    project = create_project(actor=owner, workspace=workspace, name="Task project")
    dataset = Dataset.objects.create(
        project=project,
        name="Terminal dataset",
        slug="terminal-dataset",
        created_by=owner,
    )
    version = DatasetVersion.objects.create(
        dataset=dataset,
        version_number=1,
        source_kind=DatasetSourceKind.UPLOAD,
        source_format=DatasetSourceFormat.CSV,
        source_path=f"datasets/{project.pk}/{dataset.pk}/terminal/source.csv",
        original_filename="source.csv",
        source_size_bytes=1,
        source_sha256="0" * 64,
        import_status=DatasetImportStatus.READY,
        created_by=owner,
    )

    before = ProjectActivity.objects.filter(
        project=project,
        event=ProjectActivityEvent.DATASET_READY,
    ).count()

    assert inspect_dataset_version(str(version.pk), version.inspection_generation) == "already-finished"
    version.refresh_from_db()
    assert version.import_status == DatasetImportStatus.READY
    assert ProjectActivity.objects.filter(
        project=project,
        event=ProjectActivityEvent.DATASET_READY,
    ).count() == before
