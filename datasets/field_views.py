"""Project-owned upload view for immutable observable-field NPZ sources."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import render
from django.utils.translation import gettext as _

from workspaces.permissions import can_create_dataset

from .field_forms import FieldDatasetImportForm
from .field_services import create_field_dataset_from_upload
from .views import _membership_project, _redirect_dataset


@login_required
def field_dataset_import(request, workspace_slug, project_id, project_slug):
    membership, project = _membership_project(request, workspace_slug, project_id, project_slug)
    if not can_create_dataset(request.user, project):
        raise PermissionDenied
    form = FieldDatasetImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            dataset, version = create_field_dataset_from_upload(
                actor=request.user,
                project=project,
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
                uploaded_file=form.cleaned_data["source_file"],
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            messages.success(
                request,
                _("Exact NPZ bytes stored. Safe N-dimensional array inspection has started."),
            )
            return _redirect_dataset("datasets:overview", dataset, version=version.pk)
    return render(
        request,
        "datasets/field_import.html",
        {
            "active_nav": "projects",
            "active_project_section": "datasets",
            "page_title": _("Import observable field source"),
            "workspace": membership.workspace,
            "membership": membership,
            "project": project,
            "form": form,
        },
    )
