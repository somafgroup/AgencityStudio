"""Server-rendered System identity and immutable scientific revision workflows."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from projects.models import Project
from workspaces.permissions import (
    can_archive_system,
    can_create_system,
    can_delete_system,
    can_duplicate_system,
    can_edit_system_identity,
    can_restore_system,
    can_revise_system,
)
from workspaces.services import get_workspace_membership_or_404

from .forms import (
    DeleteSystemForm,
    ObservableFormSet,
    ReferenceFormSet,
    SystemIdentityForm,
    SystemRevisionForm,
)
from .models import System
from .services import (
    archive_system,
    create_system,
    create_system_revision,
    delete_system,
    duplicate_system,
    get_system_or_404,
    restore_system,
    update_system_identity,
)
from .validation import documented_context_is_complete, validate_revision_context

REVISION_FIELDS = (
    "documentation_status",
    "description",
    "domain",
    "system_type",
    "mechanism",
    "environment",
    "measurement_context",
    "scientific_notes",
    "revision_reason",
    "a_ref_value_text",
    "a_ref_unit",
    "a_ref_origin",
    "a_ref_origin_detail",
    "a_ref_justification",
    "tau_value_text",
    "tau_unit",
    "tau_origin",
    "tau_origin_detail",
    "tau_justification",
    "w_mode",
    "w_value_text",
    "w_unit",
    "w_origin",
    "w_origin_detail",
    "w_justification",
    "p_c_mode",
    "p_c_value_text",
    "p_c_unit",
    "p_c_origin",
    "p_c_origin_detail",
    "p_c_justification",
)


def _membership_and_project(request, workspace_slug: str, project_id, project_slug: str):
    membership = get_workspace_membership_or_404(user=request.user, slug=workspace_slug)
    try:
        project = Project.objects.select_related("workspace", "created_by").get(
            pk=project_id,
            workspace=membership.workspace,
            slug=project_slug,
        )
    except Project.DoesNotExist as exc:
        raise Http404 from exc
    request.session["current_workspace_slug"] = membership.workspace.slug
    return membership, project


def _system_context(membership, project, system, *, active_system_section="overview", **extra):
    user = membership.user
    return {
        "workspace": membership.workspace,
        "membership": membership,
        "project": project,
        "system": system,
        "revision": system.current_revision,
        "active_nav": "projects",
        "active_project_section": "systems",
        "active_system_section": active_system_section,
        "page_title": system.name,
        "can_revise_system": can_revise_system(user, system),
        "can_edit_system_identity": can_edit_system_identity(user, system),
        "can_duplicate_system": can_duplicate_system(user, system),
        "can_archive_system": can_archive_system(user, system),
        "can_restore_system": can_restore_system(user, system),
        "can_delete_system": can_delete_system(user, system),
        **extra,
    }


def _observable_rows(formset) -> list[dict]:
    return [
        form.cleaned_data
        for form in formset.forms
        if getattr(form, "cleaned_data", None) and form.cleaned_data.get("name")
    ]


def _reference_rows(formset) -> list[dict]:
    return [
        form.cleaned_data
        for form in formset.forms
        if getattr(form, "cleaned_data", None)
        and (form.cleaned_data.get("citation") or form.cleaned_data.get("title"))
    ]


def _revision_initial(revision) -> dict:
    return {field: getattr(revision, field) for field in REVISION_FIELDS}


def _observable_initial(revision) -> list[dict]:
    return [
        {
            "name": item.name,
            "symbol": item.symbol,
            "description": item.description,
            "unit": item.unit,
            "observable_kind": item.observable_kind,
            "nature": item.nature,
            "source_description": item.source_description,
            "is_primary": item.is_primary,
        }
        for item in revision.observables.order_by("position")
    ]


def _reference_initial(revision) -> list[dict]:
    return [
        {
            "title": item.title,
            "citation": item.citation,
            "doi": item.doi,
            "url": item.url,
            "notes": item.notes,
            "supports_a_ref": item.supports_a_ref,
            "supports_tau": item.supports_tau,
            "supports_w": item.supports_w,
            "supports_p_c": item.supports_p_c,
        }
        for item in revision.references.all()
    ]


def _add_validation_error(form, exc: ValidationError) -> None:
    if hasattr(exc, "error_dict"):
        for field, errors in exc.error_dict.items():
            target = field if field in form.fields else None
            for error in errors:
                form.add_error(target, error)
    else:
        for message in exc.messages:
            form.add_error(None, message)


def _review_context(revision_form, observables) -> list:
    try:
        _parsed, issues = validate_revision_context(revision_form.cleaned_data, observables)
    except ValidationError as exc:
        _add_validation_error(revision_form, exc)
        return []
    return issues


def _revision_snapshot(revision) -> tuple[dict, list[dict]]:
    data = _revision_initial(revision)
    observables = _observable_initial(revision)
    try:
        _parsed, issues = validate_revision_context(data, observables)
    except ValidationError:
        issues = []
    return data, issues


@login_required
def system_list(request, workspace_slug: str, project_id, project_slug: str):
    membership, project = _membership_and_project(request, workspace_slug, project_id, project_slug)
    systems = (
        System.objects.for_project(project)
        .select_related("current_revision", "created_by")
        .prefetch_related("current_revision__observables")
    )
    status_filter = request.GET.get("status", "active")
    systems = systems.archived() if status_filter == "archived" else systems.active()
    query = request.GET.get("q", "").strip()
    if query:
        systems = systems.filter(
            Q(name__icontains=query)
            | Q(current_revision__domain__icontains=query)
            | Q(current_revision__observables__name__icontains=query)
        ).distinct()
    sort = request.GET.get("sort", "updated")
    ordering = {
        "name": ("name",),
        "created": ("-created_at",),
        "updated": ("-updated_at",),
    }.get(sort, ("-updated_at",))
    page_obj = Paginator(systems.order_by(*ordering), 20).get_page(request.GET.get("page"))
    return render(
        request,
        "systems/list.html",
        {
            "workspace": membership.workspace,
            "membership": membership,
            "project": project,
            "page_obj": page_obj,
            "query": query,
            "sort": sort,
            "status_filter": status_filter,
            "can_create_system": can_create_system(request.user, project),
            "active_nav": "projects",
            "active_project_section": "systems",
            "page_title": _("Systems"),
        },
    )


def _scientific_form_context(
    *,
    membership,
    project,
    system,
    identity_form,
    revision_form,
    observable_formset,
    reference_formset,
    review_ready=False,
    issues=None,
    is_revision=False,
):
    return {
        "workspace": membership.workspace,
        "membership": membership,
        "project": project,
        "system": system,
        "identity_form": identity_form,
        "revision_form": revision_form,
        "observable_formset": observable_formset,
        "reference_formset": reference_formset,
        "review_ready": review_ready,
        "context_issues": issues or [],
        "is_revision": is_revision,
        "active_nav": "projects",
        "active_project_section": "systems",
        "page_title": _("Revise scientific context") if is_revision else _("New system"),
    }


@login_required
def system_create(request, workspace_slug: str, project_id, project_slug: str):
    membership, project = _membership_and_project(request, workspace_slug, project_id, project_slug)
    if not can_create_system(request.user, project):
        raise PermissionDenied

    identity_form = SystemIdentityForm(request.POST or None)
    revision_form = SystemRevisionForm(request.POST or None)
    observable_formset = ObservableFormSet(request.POST or None, prefix="observables")
    reference_formset = ReferenceFormSet(request.POST or None, prefix="references")
    review_ready = False
    issues = []

    if request.method == "POST" and all(
        (
            identity_form.is_valid(),
            revision_form.is_valid(),
            observable_formset.is_valid(),
            reference_formset.is_valid(),
        )
    ):
        observables = _observable_rows(observable_formset)
        references = _reference_rows(reference_formset)
        issues = _review_context(revision_form, observables)
        intent = request.POST.get("intent", "review")
        if revision_form.errors:
            review_ready = False
        elif intent == "save":
            try:
                system = create_system(
                    actor=request.user,
                    project=project,
                    name=identity_form.cleaned_data["name"],
                    description=identity_form.cleaned_data["description"],
                    revision_data=revision_form.cleaned_data,
                    observables=observables,
                    references=references,
                )
            except ValidationError as exc:
                _add_validation_error(revision_form, exc)
            else:
                messages.success(request, _("System created with scientific Revision 1."))
                return redirect(
                    "systems:detail",
                    workspace_slug=project.workspace.slug,
                    project_id=project.pk,
                    project_slug=project.slug,
                    system_id=system.pk,
                    system_slug=system.slug,
                )
        else:
            review_ready = True

    return render(
        request,
        "systems/scientific_form.html",
        _scientific_form_context(
            membership=membership,
            project=project,
            system=None,
            identity_form=identity_form,
            revision_form=revision_form,
            observable_formset=observable_formset,
            reference_formset=reference_formset,
            review_ready=review_ready,
            issues=issues,
        ),
    )


@login_required
def system_detail(
    request,
    workspace_slug: str,
    project_id,
    project_slug: str,
    system_id,
    system_slug: str,
):
    membership, project = _membership_and_project(request, workspace_slug, project_id, project_slug)
    system = get_system_or_404(
        user=request.user,
        project=project,
        system_id=system_id,
        system_slug=system_slug,
    )
    revision = system.current_revision
    issues = []
    if revision:
        _data, issues = _revision_snapshot(revision)
    return render(
        request,
        "systems/detail.html",
        _system_context(
            membership,
            project,
            system,
            revision=revision,
            observables=revision.observables.all() if revision else [],
            references=revision.references.all() if revision else [],
            context_issues=issues,
            documented_complete=documented_context_is_complete(issues),
            revisions=system.revisions.select_related("created_by").all(),
        ),
    )


@login_required
def system_revise(
    request,
    workspace_slug: str,
    project_id,
    project_slug: str,
    system_id,
    system_slug: str,
):
    membership, project = _membership_and_project(request, workspace_slug, project_id, project_slug)
    system = get_system_or_404(
        user=request.user,
        project=project,
        system_id=system_id,
        system_slug=system_slug,
    )
    if not can_revise_system(request.user, system):
        raise PermissionDenied
    current = system.current_revision
    if current is None:
        raise Http404

    if request.method == "POST":
        revision_form = SystemRevisionForm(request.POST)
        observable_formset = ObservableFormSet(request.POST, prefix="observables")
        reference_formset = ReferenceFormSet(request.POST, prefix="references")
    else:
        revision_initial = _revision_initial(current)
        revision_initial["revision_reason"] = ""
        revision_form = SystemRevisionForm(initial=revision_initial)
        observable_formset = ObservableFormSet(
            initial=_observable_initial(current),
            prefix="observables",
        )
        reference_formset = ReferenceFormSet(
            initial=_reference_initial(current),
            prefix="references",
        )
    review_ready = False
    issues = []

    if request.method == "POST" and all(
        (
            revision_form.is_valid(),
            observable_formset.is_valid(),
            reference_formset.is_valid(),
        )
    ):
        observables = _observable_rows(observable_formset)
        references = _reference_rows(reference_formset)
        issues = _review_context(revision_form, observables)
        intent = request.POST.get("intent", "review")
        if revision_form.errors:
            review_ready = False
        elif intent == "save":
            try:
                revision = create_system_revision(
                    actor=request.user,
                    system=system,
                    revision_data=revision_form.cleaned_data,
                    observables=observables,
                    references=references,
                )
            except ValidationError as exc:
                _add_validation_error(revision_form, exc)
            else:
                messages.success(
                    request,
                    _("Scientific Revision %(revision)s created.")
                    % {"revision": revision.revision_number},
                )
                return redirect(
                    "systems:detail",
                    workspace_slug=project.workspace.slug,
                    project_id=project.pk,
                    project_slug=project.slug,
                    system_id=system.pk,
                    system_slug=system.slug,
                )
        else:
            review_ready = True

    return render(
        request,
        "systems/scientific_form.html",
        _scientific_form_context(
            membership=membership,
            project=project,
            system=system,
            identity_form=None,
            revision_form=revision_form,
            observable_formset=observable_formset,
            reference_formset=reference_formset,
            review_ready=review_ready,
            issues=issues,
            is_revision=True,
        ),
    )


@login_required
def system_revision_detail(
    request,
    workspace_slug: str,
    project_id,
    project_slug: str,
    system_id,
    system_slug: str,
    revision_number: int,
):
    membership, project = _membership_and_project(request, workspace_slug, project_id, project_slug)
    system = get_system_or_404(
        user=request.user,
        project=project,
        system_id=system_id,
        system_slug=system_slug,
    )
    try:
        revision = (
            system.revisions.select_related("created_by")
            .prefetch_related("observables", "references")
            .get(revision_number=revision_number)
        )
    except system.revisions.model.DoesNotExist as exc:
        raise Http404 from exc
    return render(
        request,
        "systems/revision_detail.html",
        _system_context(
            membership,
            project,
            system,
            active_system_section="revisions",
            revision=revision,
            is_current=system.current_revision_id == revision.pk,
            observables=revision.observables.all(),
            references=revision.references.all(),
        ),
    )


@login_required
def system_settings(
    request,
    workspace_slug: str,
    project_id,
    project_slug: str,
    system_id,
    system_slug: str,
):
    membership, project = _membership_and_project(request, workspace_slug, project_id, project_slug)
    system = get_system_or_404(
        user=request.user,
        project=project,
        system_id=system_id,
        system_slug=system_slug,
    )
    if not can_edit_system_identity(request.user, system):
        raise PermissionDenied
    form = SystemIdentityForm(request.POST or None, instance=system)
    if request.method == "POST" and form.is_valid():
        try:
            system = update_system_identity(
                actor=request.user,
                system=system,
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
            )
        except ValidationError as exc:
            _add_validation_error(form, exc)
        else:
            messages.success(
                request,
                _("System settings updated. Scientific revisions were not changed."),
            )
            return redirect(
                "systems:settings",
                workspace_slug=project.workspace.slug,
                project_id=project.pk,
                project_slug=project.slug,
                system_id=system.pk,
                system_slug=system.slug,
            )
    return render(
        request,
        "systems/settings.html",
        _system_context(
            membership,
            project,
            system,
            active_system_section="settings",
            form=form,
        ),
    )


@login_required
def system_duplicate(
    request,
    workspace_slug: str,
    project_id,
    project_slug: str,
    system_id,
    system_slug: str,
):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    _membership, project = _membership_and_project(request, workspace_slug, project_id, project_slug)
    system = get_system_or_404(
        user=request.user,
        project=project,
        system_id=system_id,
        system_slug=system_slug,
    )
    clone = duplicate_system(actor=request.user, system=system)
    messages.success(request, _("System duplicated."))
    return redirect(
        "systems:detail",
        workspace_slug=project.workspace.slug,
        project_id=project.pk,
        project_slug=project.slug,
        system_id=clone.pk,
        system_slug=clone.slug,
    )


@login_required
def system_archive(
    request,
    workspace_slug: str,
    project_id,
    project_slug: str,
    system_id,
    system_slug: str,
):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    _membership, project = _membership_and_project(request, workspace_slug, project_id, project_slug)
    system = get_system_or_404(
        user=request.user,
        project=project,
        system_id=system_id,
        system_slug=system_slug,
    )
    archived = archive_system(actor=request.user, system=system)
    messages.success(request, _("System archived."))
    return redirect(
        "systems:detail",
        workspace_slug=project.workspace.slug,
        project_id=project.pk,
        project_slug=project.slug,
        system_id=archived.pk,
        system_slug=archived.slug,
    )


@login_required
def system_restore(
    request,
    workspace_slug: str,
    project_id,
    project_slug: str,
    system_id,
    system_slug: str,
):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    _membership, project = _membership_and_project(request, workspace_slug, project_id, project_slug)
    system = get_system_or_404(
        user=request.user,
        project=project,
        system_id=system_id,
        system_slug=system_slug,
    )
    restored = restore_system(actor=request.user, system=system)
    messages.success(request, _("System restored."))
    return redirect(
        "systems:detail",
        workspace_slug=project.workspace.slug,
        project_id=project.pk,
        project_slug=project.slug,
        system_id=restored.pk,
        system_slug=restored.slug,
    )


@login_required
def system_delete(
    request,
    workspace_slug: str,
    project_id,
    project_slug: str,
    system_id,
    system_slug: str,
):
    membership, project = _membership_and_project(request, workspace_slug, project_id, project_slug)
    system = get_system_or_404(
        user=request.user,
        project=project,
        system_id=system_id,
        system_slug=system_slug,
    )
    if not can_delete_system(request.user, system):
        raise PermissionDenied
    form = DeleteSystemForm(request.POST or None, system_name=system.name)
    if request.method == "POST" and form.is_valid():
        delete_system(actor=request.user, system=system)
        messages.success(request, _("System permanently deleted."))
        return redirect(
            "systems:project-list",
            workspace_slug=project.workspace.slug,
            project_id=project.pk,
            project_slug=project.slug,
        )
    return render(
        request,
        "systems/delete.html",
        _system_context(
            membership,
            project,
            system,
            active_system_section="settings",
            form=form,
        ),
    )
