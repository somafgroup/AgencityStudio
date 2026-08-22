import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from projects.models import Project, ProjectActivityEvent, ProjectStatus
from projects.services import (
    archive_project,
    create_project,
    delete_project,
    duplicate_project,
    restore_project,
    update_project,
)
from workspaces.models import WorkspaceMembership, WorkspaceRole
from workspaces.permissions import (
    can_create_project,
    can_delete_project,
    can_edit_project,
    can_view_project,
)
from workspaces.services import create_organisation_workspace, delete_organisation_workspace

User = get_user_model()
PASSWORD = "Scientific-Plan3-Password!42"


def make_user(email: str, **extra):
    return User.objects.create_user(email=email, password=PASSWORD, **extra)


def make_project(owner, workspace, name="Rotor vibration study"):
    return create_project(
        actor=owner,
        workspace=workspace,
        name=name,
        description="Baseline scientific context",
        domain="mechanics",
        tags=["vibration", "rotor"],
        notes="Project-level notes only.",
    )


@pytest.mark.django_db
def test_project_has_stable_uuid_workspace_owner_creator_and_workspace_scoped_slug():
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Dynamics Lab")

    first = make_project(owner, workspace)
    second = make_project(owner, workspace)

    assert isinstance(first.pk, uuid.UUID)
    assert first.workspace == workspace
    assert first.created_by == owner
    assert first.slug == "rotor-vibration-study"
    assert second.slug == "rotor-vibration-study-2"
    assert first.status == ProjectStatus.ACTIVE


@pytest.mark.django_db
def test_project_permissions_inherit_workspace_roles_without_staff_bypass():
    owner = make_user("owner@example.com")
    editor = make_user("editor@example.com")
    analyst = make_user("analyst@example.com")
    viewer = make_user("viewer@example.com")
    staff = make_user("staff@example.com", is_staff=True)
    workspace = create_organisation_workspace(owner=owner, name="Permission Lab")
    WorkspaceMembership.objects.create(user=editor, workspace=workspace, role=WorkspaceRole.EDITOR)
    WorkspaceMembership.objects.create(user=analyst, workspace=workspace, role=WorkspaceRole.ANALYST)
    WorkspaceMembership.objects.create(user=viewer, workspace=workspace, role=WorkspaceRole.VIEWER)
    project = make_project(owner, workspace)

    assert can_create_project(owner, workspace)
    assert can_create_project(editor, workspace)
    assert can_edit_project(owner, project)
    assert can_edit_project(editor, project)
    assert can_delete_project(owner, project)
    assert not can_delete_project(editor, project)
    assert can_view_project(analyst, project)
    assert can_view_project(viewer, project)
    assert not can_edit_project(analyst, project)
    assert not can_edit_project(viewer, project)
    assert not can_view_project(staff, project)


@pytest.mark.django_db
def test_create_endpoint_uses_current_workspace_and_ignores_sensitive_post_fields(client):
    owner = make_user("owner@example.com")
    other = make_user("other@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Current Workspace")
    forbidden = create_organisation_workspace(owner=other, name="Forbidden Workspace")
    client.force_login(owner)
    session = client.session
    session["current_workspace_slug"] = workspace.slug
    session.save()

    response = client.post(
        reverse("projects:create"),
        {
            "name": "Controlled Project",
            "description": "Created through form",
            "domain": "robotics",
            "tags": "control, actuator",
            "notes": "",
            "workspace": forbidden.pk,
            "created_by": other.pk,
            "status": ProjectStatus.ARCHIVED,
        },
    )

    assert response.status_code == 302
    project = Project.objects.get(name="Controlled Project")
    assert project.workspace == workspace
    assert project.created_by == owner
    assert project.status == ProjectStatus.ACTIVE


@pytest.mark.django_db
def test_non_member_cannot_confirm_private_project_exists(client):
    owner = make_user("owner@example.com")
    outsider = make_user("outsider@example.com", is_staff=True)
    workspace = create_organisation_workspace(owner=owner, name="Private Project Lab")
    project = make_project(owner, workspace, name="Confidential Rotor")
    client.force_login(outsider)

    response = client.get(
        reverse(
            "projects:overview",
            args=[workspace.slug, project.pk, project.slug],
        )
    )

    assert response.status_code == 404
    assert b"Confidential Rotor" not in response.content


@pytest.mark.django_db
def test_viewer_can_open_project_but_direct_mutation_routes_are_denied(client):
    owner = make_user("owner@example.com")
    viewer = make_user("viewer@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Read Only Lab")
    WorkspaceMembership.objects.create(user=viewer, workspace=workspace, role=WorkspaceRole.VIEWER)
    project = make_project(owner, workspace)
    client.force_login(viewer)
    args = [workspace.slug, project.pk, project.slug]

    assert client.get(reverse("projects:overview", args=args)).status_code == 200
    assert client.get(reverse("projects:settings", args=args)).status_code == 403
    assert client.post(reverse("projects:archive", args=args)).status_code == 403


@pytest.mark.django_db
def test_archive_restore_updates_querysets_and_activity():
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Lifecycle Lab")
    project = make_project(owner, workspace)

    archive_project(actor=owner, project=project)
    project.refresh_from_db()
    assert project.status == ProjectStatus.ARCHIVED
    assert project.archived_at is not None
    assert not Project.objects.active().filter(pk=project.pk).exists()
    assert Project.objects.archived().filter(pk=project.pk).exists()

    restore_project(actor=owner, project=project)
    project.refresh_from_db()
    assert project.status == ProjectStatus.ACTIVE
    assert project.archived_at is None
    assert Project.objects.active().filter(pk=project.pk).exists()
    assert list(project.activity.values_list("event", flat=True))[:3] == [
        ProjectActivityEvent.RESTORED,
        ProjectActivityEvent.ARCHIVED,
        ProjectActivityEvent.CREATED,
    ]


@pytest.mark.django_db
def test_duplicate_copies_metadata_not_identity_status_or_activity_history():
    owner = make_user("owner@example.com")
    editor = make_user("editor@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Duplication Lab")
    WorkspaceMembership.objects.create(user=editor, workspace=workspace, role=WorkspaceRole.EDITOR)
    source = make_project(owner, workspace)
    update_project(
        actor=owner,
        project=source,
        name=source.name,
        description="Updated description",
        domain=source.domain,
        tags=source.tags,
        notes=source.notes,
    )
    archive_project(actor=owner, project=source)
    source.refresh_from_db()

    clone = duplicate_project(actor=editor, project=source)

    assert clone.pk != source.pk
    assert clone.slug != source.slug
    assert clone.workspace == source.workspace
    assert clone.created_by == editor
    assert clone.description == source.description
    assert clone.domain == source.domain
    assert clone.tags == source.tags
    assert clone.notes == source.notes
    assert clone.status == ProjectStatus.ACTIVE
    assert clone.archived_at is None
    assert list(clone.activity.values_list("event", flat=True)) == [ProjectActivityEvent.DUPLICATED]


@pytest.mark.django_db
def test_project_slug_remains_stable_when_project_is_renamed():
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Stable URL Lab")
    project = make_project(owner, workspace)
    original_slug = project.slug

    updated = update_project(
        actor=owner,
        project=project,
        name="Renamed experiment",
        description=project.description,
        domain=project.domain,
        tags=project.tags,
        notes=project.notes,
    )

    assert updated.name == "Renamed experiment"
    assert updated.slug == original_slug


@pytest.mark.django_db
def test_creator_deletion_never_deletes_workspace_project():
    owner = make_user("owner@example.com")
    creator = make_user("creator@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Durable Lab")
    WorkspaceMembership.objects.create(user=creator, workspace=workspace, role=WorkspaceRole.EDITOR)
    project = make_project(creator, workspace)

    creator.delete()
    project.refresh_from_db()

    assert project.workspace == workspace
    assert project.created_by is None


@pytest.mark.django_db
def test_workspace_with_projects_cannot_be_deleted_implicitly():
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Protected Lab")
    make_project(owner, workspace)

    with pytest.raises(ValidationError, match="contains projects"):
        delete_organisation_workspace(actor=owner, workspace=workspace)

    assert workspace.projects.exists()


@pytest.mark.django_db
def test_only_owner_can_permanently_delete_project():
    owner = make_user("owner@example.com")
    editor = make_user("editor@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Deletion Lab")
    WorkspaceMembership.objects.create(user=editor, workspace=workspace, role=WorkspaceRole.EDITOR)
    project = make_project(owner, workspace)

    with pytest.raises(PermissionDenied):
        delete_project(actor=editor, project=project)
    assert Project.objects.filter(pk=project.pk).exists()

    delete_project(actor=owner, project=project)
    assert not Project.objects.filter(pk=project.pk).exists()
