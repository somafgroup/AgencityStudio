"""Central object-level permission policies for Workspaces and their owned content."""

from django.contrib.auth.models import AnonymousUser

from .models import Workspace, WorkspaceMembership, WorkspaceRole

WRITE_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.EDITOR}
PREPARATION_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.EDITOR, WorkspaceRole.ANALYST}


def membership_for(user, workspace: Workspace) -> WorkspaceMembership | None:
    """Return the explicit workspace membership for an authenticated user."""
    if isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
        return None
    return WorkspaceMembership.objects.filter(user=user, workspace=workspace).first()


def can_view_workspace(user, workspace: Workspace) -> bool:
    return membership_for(user, workspace) is not None


def can_edit_workspace(user, workspace: Workspace) -> bool:
    """Return whether the role may edit normal workspace-owned content."""
    membership = membership_for(user, workspace)
    return membership is not None and membership.role in WRITE_ROLES


def can_manage_members(user, workspace: Workspace) -> bool:
    membership = membership_for(user, workspace)
    return membership is not None and membership.role == WorkspaceRole.OWNER


def can_manage_workspace(user, workspace: Workspace) -> bool:
    return can_manage_members(user, workspace)


def can_delete_workspace(user, workspace: Workspace) -> bool:
    return not workspace.is_personal and can_manage_workspace(user, workspace)


def can_create_project(user, workspace: Workspace) -> bool:
    return can_edit_workspace(user, workspace)


def can_view_project(user, project) -> bool:
    return can_view_workspace(user, project.workspace)


def can_edit_project(user, project) -> bool:
    return can_edit_workspace(user, project.workspace)


def can_archive_project(user, project) -> bool:
    return can_edit_project(user, project)


def can_restore_project(user, project) -> bool:
    return can_edit_project(user, project)


def can_duplicate_project(user, project) -> bool:
    return can_edit_project(user, project)


def can_delete_project(user, project) -> bool:
    membership = membership_for(user, project.workspace)
    return membership is not None and membership.role == WorkspaceRole.OWNER


def can_create_dataset(user, project) -> bool:
    """Owners and Editors may add raw data to active Projects."""
    return getattr(project, "status", None) == "ACTIVE" and can_edit_project(user, project)


def can_view_dataset(user, dataset) -> bool:
    return can_view_project(user, dataset.project)


def can_download_dataset(user, dataset) -> bool:
    return can_view_dataset(user, dataset)


def can_edit_dataset(user, dataset) -> bool:
    return getattr(dataset.project, "status", None) == "ACTIVE" and can_edit_project(
        user, dataset.project
    )


def can_add_dataset_version(user, dataset) -> bool:
    return can_edit_dataset(user, dataset)


def can_annotate_dataset(user, dataset) -> bool:
    return can_edit_dataset(user, dataset)


def can_confirm_dataset_version(user, dataset) -> bool:
    return can_edit_dataset(user, dataset)


def can_delete_dataset(user, dataset) -> bool:
    membership = membership_for(user, dataset.project.workspace)
    return membership is not None and membership.role == WorkspaceRole.OWNER


def can_create_preparation(user, dataset) -> bool:
    """Allow scientific derived work without granting raw-source mutation rights."""
    if getattr(dataset.project, "status", None) != "ACTIVE":
        return False
    membership = membership_for(user, dataset.project.workspace)
    return membership is not None and membership.role in PREPARATION_ROLES


def can_view_preparation(user, preparation) -> bool:
    return can_view_dataset(user, preparation.source_version.dataset)


def can_edit_preparation(user, preparation) -> bool:
    return preparation.status == "DRAFT" and can_create_preparation(
        user, preparation.source_version.dataset
    )


def can_run_preparation(user, preparation) -> bool:
    return can_edit_preparation(user, preparation)


def can_duplicate_preparation(user, preparation) -> bool:
    return can_create_preparation(user, preparation.source_version.dataset)


def can_download_prepared_data(user, preparation) -> bool:
    return can_view_preparation(user, preparation)


def can_delete_preparation(user, preparation) -> bool:
    membership = membership_for(user, preparation.source_version.dataset.project.workspace)
    return membership is not None and membership.role == WorkspaceRole.OWNER
