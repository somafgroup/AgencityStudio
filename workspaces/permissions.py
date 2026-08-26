"""Central object-level permission policies for Workspaces and their owned content."""

from django.contrib.auth.models import AnonymousUser

from .models import Workspace, WorkspaceMembership, WorkspaceRole

WRITE_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.EDITOR}
PREPARATION_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.EDITOR, WorkspaceRole.ANALYST}
SYSTEM_AUTHOR_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.EDITOR, WorkspaceRole.ANALYST}
ANALYSIS_AUTHOR_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.EDITOR, WorkspaceRole.ANALYST}


def membership_for(user, workspace: Workspace) -> WorkspaceMembership | None:
    """Return the explicit workspace membership for an authenticated user."""
    if isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
        return None
    return WorkspaceMembership.objects.filter(user=user, workspace=workspace).first()


def can_view_workspace(user, workspace: Workspace) -> bool:
    return membership_for(user, workspace) is not None


def can_edit_workspace(user, workspace: Workspace) -> bool:
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
    return getattr(project, "status", None) == "ACTIVE" and can_edit_project(user, project)


def can_view_dataset(user, dataset) -> bool:
    return can_view_project(user, dataset.project)


def can_download_dataset(user, dataset) -> bool:
    return can_view_dataset(user, dataset)


def can_edit_dataset(user, dataset) -> bool:
    return getattr(dataset.project, "status", None) == "ACTIVE" and can_edit_project(user, dataset.project)


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
    if getattr(dataset.project, "status", None) != "ACTIVE":
        return False
    membership = membership_for(user, dataset.project.workspace)
    return membership is not None and membership.role in PREPARATION_ROLES


def can_view_preparation(user, preparation) -> bool:
    return can_view_dataset(user, preparation.source_version.dataset)


def can_edit_preparation(user, preparation) -> bool:
    return preparation.status == "DRAFT" and can_create_preparation(user, preparation.source_version.dataset)


def can_run_preparation(user, preparation) -> bool:
    return can_edit_preparation(user, preparation)


def can_duplicate_preparation(user, preparation) -> bool:
    return can_create_preparation(user, preparation.source_version.dataset)


def can_download_prepared_data(user, preparation) -> bool:
    return can_view_preparation(user, preparation)


def can_delete_preparation(user, preparation) -> bool:
    membership = membership_for(user, preparation.source_version.dataset.project.workspace)
    return membership is not None and membership.role == WorkspaceRole.OWNER


def can_create_system(user, project) -> bool:
    if getattr(project, "status", None) != "ACTIVE":
        return False
    membership = membership_for(user, project.workspace)
    return membership is not None and membership.role in SYSTEM_AUTHOR_ROLES


def can_view_system(user, system) -> bool:
    return can_view_project(user, system.project)


def can_revise_system(user, system) -> bool:
    return getattr(system, "status", None) == "ACTIVE" and can_create_system(user, system.project)


def can_duplicate_system(user, system) -> bool:
    return can_create_system(user, system.project)


def can_edit_system_identity(user, system) -> bool:
    return getattr(system.project, "status", None) == "ACTIVE" and can_edit_project(user, system.project)


def can_archive_system(user, system) -> bool:
    return can_edit_system_identity(user, system)


def can_restore_system(user, system) -> bool:
    return can_edit_project(user, system.project)


def can_delete_system(user, system) -> bool:
    membership = membership_for(user, system.project.workspace)
    return membership is not None and membership.role == WorkspaceRole.OWNER


def can_create_analysis(user, project) -> bool:
    """Owners, Editors and Analysts may create scientific runs in active Projects."""
    if getattr(project, "status", None) != "ACTIVE":
        return False
    membership = membership_for(user, project.workspace)
    return membership is not None and membership.role in ANALYSIS_AUTHOR_ROLES


def can_view_analysis(user, analysis) -> bool:
    return can_view_project(user, analysis.project)


def can_edit_analysis(user, analysis) -> bool:
    return getattr(analysis, "status", None) == "ACTIVE" and can_create_analysis(user, analysis.project)


def can_run_analysis(user, analysis) -> bool:
    return can_edit_analysis(user, analysis)


def can_archive_analysis(user, analysis) -> bool:
    membership = membership_for(user, analysis.project.workspace)
    return (
        getattr(analysis.project, "status", None) == "ACTIVE"
        and membership is not None
        and membership.role in WRITE_ROLES
    )


def can_restore_analysis(user, analysis) -> bool:
    membership = membership_for(user, analysis.project.workspace)
    return membership is not None and membership.role in WRITE_ROLES


def can_delete_analysis(user, analysis) -> bool:
    membership = membership_for(user, analysis.project.workspace)
    return membership is not None and membership.role == WorkspaceRole.OWNER


def can_view_analysis_result(user, run) -> bool:
    return can_view_analysis(user, run.analysis)


def can_run_diagnostics(user, run) -> bool:
    """Owners, Editors and Analysts may derive diagnostics from a completed Run."""
    return getattr(run, "status", None) == "COMPLETED" and can_run_analysis(user, run.analysis)


def can_view_diagnostic_run(user, diagnostic_run) -> bool:
    return can_view_analysis_result(user, diagnostic_run.analysis_run)
