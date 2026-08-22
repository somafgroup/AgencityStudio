"""Server-rendered workspace workflows with object-level permission enforcement."""

from smtplib import SMTPException

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from .forms import (
    DeleteWorkspaceForm,
    InvitationForm,
    OrganisationWorkspaceForm,
    RoleChangeForm,
    WorkspaceSettingsForm,
)
from .models import InvitationStatus, WorkspaceInvitation, WorkspaceMembership
from .permissions import can_delete_workspace, can_manage_members, can_manage_workspace
from .services import (
    accept_invitation,
    change_member_role,
    create_organisation_workspace,
    delete_organisation_workspace,
    get_workspace_membership_or_404,
    invite_member,
    remove_member,
    resolve_invitation,
    revoke_invitation,
    update_workspace,
)


User = get_user_model()


def _workspace_context(membership: WorkspaceMembership, **extra):
    return {
        "workspace": membership.workspace,
        "membership": membership,
        "active_nav": "workspace",
        "page_title": membership.workspace.name,
        "can_manage_members": can_manage_members(membership.user, membership.workspace),
        "can_manage_workspace": can_manage_workspace(membership.user, membership.workspace),
        **extra,
    }


@login_required

def workspace_list(request):
    memberships = (
        WorkspaceMembership.objects.filter(user=request.user)
        .select_related("workspace")
        .order_by("workspace__type", "workspace__name")
    )
    return render(
        request,
        "workspaces/list.html",
        {"memberships": memberships, "active_nav": "workspace", "page_title": _("Workspaces")},
    )


@login_required

def create_workspace(request):
    form = OrganisationWorkspaceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        workspace = create_organisation_workspace(
            owner=request.user,
            name=form.cleaned_data["name"],
            description=form.cleaned_data["description"],
        )
        request.session["current_workspace_slug"] = workspace.slug
        messages.success(request, _("Organisation workspace created."))
        return redirect("workspaces:overview", slug=workspace.slug)
    return render(
        request,
        "workspaces/create.html",
        {"form": form, "active_nav": "workspace", "page_title": _("New workspace")},
    )


@login_required

def overview(request, slug: str):
    membership = get_workspace_membership_or_404(user=request.user, slug=slug)
    request.session["current_workspace_slug"] = membership.workspace.slug
    member_count = membership.workspace.memberships.count()
    return render(
        request,
        "workspaces/overview.html",
        _workspace_context(membership, member_count=member_count),
    )


@login_required

def activate_workspace(request, slug: str):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    membership = get_workspace_membership_or_404(user=request.user, slug=slug)
    request.session["current_workspace_slug"] = membership.workspace.slug
    return redirect("workspaces:overview", slug=slug)


@login_required

def settings_view(request, slug: str):
    membership = get_workspace_membership_or_404(user=request.user, slug=slug)
    workspace = membership.workspace
    if not can_manage_workspace(request.user, workspace):
        raise PermissionDenied
    form = WorkspaceSettingsForm(
        request.POST or None,
        initial={"name": workspace.name, "description": workspace.description},
    )
    if request.method == "POST" and form.is_valid():
        update_workspace(
            actor=request.user,
            workspace=workspace,
            name=form.cleaned_data["name"],
            description=form.cleaned_data["description"],
        )
        messages.success(request, _("Workspace settings updated."))
        return redirect("workspaces:settings", slug=slug)
    return render(
        request,
        "workspaces/settings.html",
        _workspace_context(
            membership,
            form=form,
            can_delete_workspace=can_delete_workspace(request.user, workspace),
        ),
    )


@login_required

def members(request, slug: str):
    membership = get_workspace_membership_or_404(user=request.user, slug=slug)
    workspace = membership.workspace
    memberships = workspace.memberships.select_related("user").order_by("joined_at")
    invitations = workspace.invitations.filter(status=InvitationStatus.PENDING).order_by("-created_at")
    return render(
        request,
        "workspaces/members.html",
        _workspace_context(
            membership,
            memberships=memberships,
            invitations=invitations,
        ),
    )


def _send_invitation_email(request, invitation: WorkspaceInvitation, token: str) -> None:
    accept_url = request.build_absolute_uri(
        reverse("workspaces:accept-invitation", kwargs={"token": token})
    )
    send_mail(
        subject=_("You were invited to an AgencityStudio workspace"),
        message=_(
            "You were invited to %(workspace)s as %(role)s.\n\n"
            "Open this secure link to continue:\n%(url)s\n\n"
            "This invitation expires automatically."
        )
        % {
            "workspace": invitation.workspace.name,
            "role": invitation.get_role_display(),
            "url": accept_url,
        },
        from_email=None,
        recipient_list=[invitation.email],
        fail_silently=False,
    )


@login_required

def invite(request, slug: str):
    membership = get_workspace_membership_or_404(user=request.user, slug=slug)
    if not can_manage_members(request.user, membership.workspace):
        raise PermissionDenied
    form = InvitationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            invitation, token = invite_member(
                actor=request.user,
                workspace=membership.workspace,
                email=form.cleaned_data["email"],
                role=form.cleaned_data["role"],
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            try:
                _send_invitation_email(request, invitation, token)
            except (OSError, SMTPException):
                messages.warning(
                    request,
                    _("The invitation was saved, but the email could not be delivered."),
                )
            else:
                messages.success(request, _("Invitation sent."))
            return redirect("workspaces:members", slug=slug)
    return render(
        request,
        "workspaces/invite.html",
        _workspace_context(membership, form=form),
    )


@login_required

def change_role(request, slug: str, membership_id: int):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    actor_membership = get_workspace_membership_or_404(user=request.user, slug=slug)
    if not can_manage_members(request.user, actor_membership.workspace):
        raise PermissionDenied
    try:
        target = actor_membership.workspace.memberships.select_related("workspace", "user").get(
            pk=membership_id
        )
    except WorkspaceMembership.DoesNotExist as exc:
        raise Http404 from exc
    form = RoleChangeForm(request.POST)
    if form.is_valid():
        try:
            change_member_role(actor=request.user, membership=target, role=form.cleaned_data["role"])
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(request, _("Member role updated."))
    return redirect("workspaces:members", slug=slug)


@login_required

def remove_member_view(request, slug: str, membership_id: int):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    actor_membership = get_workspace_membership_or_404(user=request.user, slug=slug)
    try:
        target = actor_membership.workspace.memberships.select_related("workspace", "user").get(
            pk=membership_id
        )
    except WorkspaceMembership.DoesNotExist as exc:
        raise Http404 from exc
    try:
        remove_member(actor=request.user, membership=target)
    except ValidationError as exc:
        messages.error(request, exc.message)
    messages.success(request, _("Member removed."))
    return redirect("workspaces:members", slug=slug)


@login_required

def leave_workspace(request, slug: str):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    membership = get_workspace_membership_or_404(user=request.user, slug=slug)
    try:
        remove_member(actor=request.user, membership=membership)
    except ValidationError as exc:
        messages.error(request, exc.message)
        return redirect("workspaces:overview", slug=slug)
    messages.success(request, _("You left the workspace."))
    return redirect("dashboard")


@login_required

def revoke_invitation_view(request, slug: str, invitation_id: int):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    membership = get_workspace_membership_or_404(user=request.user, slug=slug)
    if not can_manage_members(request.user, membership.workspace):
        raise PermissionDenied
    try:
        invitation = membership.workspace.invitations.get(pk=invitation_id)
    except WorkspaceInvitation.DoesNotExist as exc:
        raise Http404 from exc
    try:
        revoke_invitation(actor=request.user, invitation=invitation)
    except ValidationError as exc:
        messages.error(request, exc.message)
    else:
        messages.success(request, _("Invitation revoked."))
    return redirect("workspaces:members", slug=slug)


@login_required

def delete_workspace_view(request, slug: str):
    membership = get_workspace_membership_or_404(user=request.user, slug=slug)
    workspace = membership.workspace
    if not can_delete_workspace(request.user, workspace):
        raise PermissionDenied
    form = DeleteWorkspaceForm(request.POST or None, workspace_name=workspace.name)
    if request.method == "POST" and form.is_valid():
        delete_organisation_workspace(actor=request.user, workspace=workspace)
        request.session.pop("current_workspace_slug", None)
        messages.success(request, _("Workspace deleted."))
        return redirect("dashboard")
    return render(
        request,
        "workspaces/delete.html",
        _workspace_context(membership, form=form),
    )


def accept_invitation_view(request, token: str):
    invitation = resolve_invitation(token)
    if invitation is None:
        raise Http404
    if invitation.status != InvitationStatus.PENDING:
        return render(
            request,
            "workspaces/invitation_accept.html",
            {"invitation": invitation, "invitation_unavailable": True, "page_title": _("Invitation")},
            status=410,
        )

    if not request.user.is_authenticated:
        account_exists = User.objects.filter(email__iexact=invitation.email).exists()
        return render(
            request,
            "workspaces/invitation_accept.html",
            {
                "invitation": invitation,
                "token": token,
                "account_exists": account_exists,
                "page_title": _("Workspace invitation"),
            },
        )

    if request.user.email.lower() != invitation.email.lower():
        raise PermissionDenied(_("Sign in with the email address that received this invitation."))

    if request.method == "POST":
        try:
            membership = accept_invitation(user=request.user, token=token)
        except ValidationError as exc:
            messages.error(request, exc.message)
            return redirect("workspaces:accept-invitation", token=token)
        request.session["current_workspace_slug"] = membership.workspace.slug
        messages.success(request, _("Invitation accepted."))
        return redirect("workspaces:overview", slug=membership.workspace.slug)

    return render(
        request,
        "workspaces/invitation_accept.html",
        {"invitation": invitation, "token": token, "page_title": _("Workspace invitation")},
    )
