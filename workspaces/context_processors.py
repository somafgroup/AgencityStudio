"""Template context for authenticated workspace navigation."""

from .services import workspace_memberships_for


def workspace_context(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {
            "workspace_memberships": (),
            "current_workspace": None,
            "current_workspace_membership": None,
        }

    memberships = list(workspace_memberships_for(user))
    if not memberships:
        return {
            "workspace_memberships": (),
            "current_workspace": None,
            "current_workspace_membership": None,
        }

    preferred_slug = request.session.get("current_workspace_slug")
    current = next(
        (membership for membership in memberships if membership.workspace.slug == preferred_slug),
        None,
    )
    if current is None:
        current = next((membership for membership in memberships if membership.workspace.is_personal), None)
    if current is None:
        current = memberships[0]

    request.session["current_workspace_slug"] = current.workspace.slug
    return {
        "workspace_memberships": memberships,
        "current_workspace": current.workspace,
        "current_workspace_membership": current,
        "current_workspace_role": current.get_role_display(),
    }
