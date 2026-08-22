"""Central object-level permission policies for workspaces."""

from django.contrib.auth.models import AnonymousUser

from .models import Workspace, WorkspaceMembership, WorkspaceRole

WRITE_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.EDITOR}


def membership_for(user, workspace: Workspace) -> WorkspaceMembership | None:
    """Return the explicit workspace membership for an authenticated user."""
    if isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
        return None
    return WorkspaceMembership.objects.filter(user=user, workspace=workspace).first()


def can_view_workspace(user, workspace: Workspace) -> bool:
    return membership_for(user, workspace) is not None


def can_edit_workspace(user, workspace: Workspace) -> bool:
    """Return whether the role may edit normal future workspace content."""
    membership = membership_for(user, workspace)
    return membership is not None and membership.role in WRITE_ROLES


def can_manage_members(user, workspace: Workspace) -> bool:
    membership = membership_for(user, workspace)
    return membership is not None and membership.role == WorkspaceRole.OWNER


def can_manage_workspace(user, workspace: Workspace) -> bool:
    return can_manage_members(user, workspace)


def can_delete_workspace(user, workspace: Workspace) -> bool:
    return not workspace.is_personal and can_manage_workspace(user, workspace)
