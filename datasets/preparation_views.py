"""Server-rendered workflows for explicit, immutable data preparations."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from workspaces.permissions import (
    can_create_preparation,
    can_delete_preparation,
    can_download_prepared_data,
    can_duplicate_preparation,
    can_edit_preparation,
    can_run_preparation,
)

from .forms import DeletePreparationForm, PreparationCreateForm, PreparationStepForm
from .models import DataPreparation, DataPreparationStatus, DatasetImportStatus
from .preparation import OPERATION_LABELS
from .preparation_services import (
    add_preparation_step,
    create_preparation,
    delete_preparation,
    duplicate_preparation,
    get_preparation_or_404,
    move_preparation_step,
    prepared_preview_page,
    remove_preparation_step,
    rerun_preparation,
    run_preparation,
)
from .storage import dataset_storage
from .views import _dataset_context, _membership_project_dataset, _selected_version


def _preparation_context(request, membership, project, dataset, preparation, **extra):
    return _dataset_context(
        request,
        membership,
        project,
        dataset,
        active_section="prepare",
        version=preparation.source_version,
        preparation=preparation,
        can_edit_preparation=can_edit_preparation(request.user, preparation),
        can_run_preparation=can_run_preparation(request.user, preparation),
        can_duplicate_preparation=can_duplicate_preparation(request.user, preparation),
        can_delete_preparation=can_delete_preparation(request.user, preparation),
        can_download_prepared=can_download_prepared_data(request.user, preparation),
        operation_labels=OPERATION_LABELS,
        **extra,
    )


def _redirect_preparation(preparation, view_name="datasets:preparation-detail"):
    dataset = preparation.source_version.dataset
    return redirect(
        view_name,
        workspace_slug=dataset.project.workspace.slug,
        project_id=dataset.project_id,
        project_slug=dataset.project.slug,
        dataset_id=dataset.pk,
        dataset_slug=dataset.slug,
        preparation_id=preparation.pk,
    )


@login_required
def preparation_list(request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug):
    membership, project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    version = _selected_version(request, dataset)
    preparations = (
        DataPreparation.objects.filter(source_version__dataset=dataset)
        .select_related("source_version", "created_by")
        .order_by("-created_at")
    )
    return render(
        request,
        "datasets/preparations/list.html",
        _dataset_context(
            request,
            membership,
            project,
            dataset,
            active_section="prepare",
            version=version,
            preparations=preparations,
            can_create_preparation=(
                version is not None
                and version.import_status == DatasetImportStatus.READY
                and can_create_preparation(request.user, dataset)
            ),
        ),
    )


@login_required
def preparation_create(request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug):
    membership, project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    version = _selected_version(request, dataset)
    if version is None or version.import_status != DatasetImportStatus.READY:
        raise Http404
    if not can_create_preparation(request.user, dataset):
        raise PermissionDenied
    form = PreparationCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            preparation = create_preparation(
                actor=request.user,
                source_version=version,
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            messages.success(request, _("Preparation draft created. Add explicit transformations before running."))
            return _redirect_preparation(preparation)
    return render(
        request,
        "datasets/preparations/create.html",
        _dataset_context(
            request,
            membership,
            project,
            dataset,
            active_section="prepare",
            version=version,
            form=form,
        ),
    )


@login_required
def preparation_detail(
    request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug, preparation_id
):
    membership, project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    preparation = get_preparation_or_404(
        user=request.user, dataset=dataset, preparation_id=preparation_id
    )
    preparation = (
        DataPreparation.objects.select_related("source_version", "created_by")
        .prefetch_related("source_version__columns")
        .get(pk=preparation.pk)
    )
    step_form = PreparationStepForm(version=preparation.source_version)
    artifact = getattr(preparation, "artifact", None)
    source_missing = sum(column.missing_count for column in preparation.source_version.columns.all())
    prepared_missing = (
        sum(int(column.get("missing_count", 0)) for column in artifact.column_metadata)
        if artifact
        else None
    )
    return render(
        request,
        "datasets/preparations/detail.html",
        _preparation_context(
            request,
            membership,
            project,
            dataset,
            preparation,
            step_form=step_form,
            artifact=artifact,
            source_missing=source_missing,
            prepared_missing=prepared_missing,
        ),
    )


@login_required
def preparation_status(
    request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug, preparation_id
):
    membership, project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    preparation = get_preparation_or_404(
        user=request.user, dataset=dataset, preparation_id=preparation_id
    )
    return render(
        request,
        "datasets/preparations/_status.html",
        _preparation_context(request, membership, project, dataset, preparation),
    )


@login_required
def preparation_add_step(
    request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug, preparation_id
):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    _membership, _project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    preparation = get_preparation_or_404(
        user=request.user, dataset=dataset, preparation_id=preparation_id
    )
    if not can_edit_preparation(request.user, preparation):
        raise PermissionDenied
    form = PreparationStepForm(request.POST, version=preparation.source_version)
    if form.is_valid():
        try:
            step = form.step()
            add_preparation_step(actor=request.user, preparation=preparation, step=step)
        except (ValidationError, forms.ValidationError) as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, _("Transformation added."))
    else:
        messages.error(request, _("Review the transformation parameters and try again."))
    return _redirect_preparation(preparation)


@login_required
def preparation_step_action(
    request,
    workspace_slug,
    project_id,
    project_slug,
    dataset_id,
    dataset_slug,
    preparation_id,
    step_index,
    action,
):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    _membership, _project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    preparation = get_preparation_or_404(
        user=request.user, dataset=dataset, preparation_id=preparation_id
    )
    try:
        if action == "remove":
            remove_preparation_step(actor=request.user, preparation=preparation, index=step_index)
        elif action in {"up", "down"}:
            move_preparation_step(
                actor=request.user,
                preparation=preparation,
                index=step_index,
                direction=action,
            )
        else:
            raise Http404
    except ValidationError as exc:
        messages.error(request, exc.message)
    return _redirect_preparation(preparation)


@login_required
def preparation_run(
    request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug, preparation_id
):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    _membership, _project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    preparation = get_preparation_or_404(
        user=request.user, dataset=dataset, preparation_id=preparation_id
    )
    try:
        run_preparation(actor=request.user, preparation=preparation)
    except ValidationError as exc:
        messages.error(request, exc.message)
    else:
        messages.success(request, _("Preparation queued. The immutable source remains unchanged."))
    return _redirect_preparation(preparation)


@login_required
def preparation_duplicate(
    request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug, preparation_id
):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    _membership, _project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    preparation = get_preparation_or_404(
        user=request.user, dataset=dataset, preparation_id=preparation_id
    )
    clone = duplicate_preparation(actor=request.user, preparation=preparation)
    messages.success(request, _("Preparation duplicated as an editable draft."))
    return _redirect_preparation(clone)


@login_required
def preparation_rerun(
    request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug, preparation_id
):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    _membership, _project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    preparation = get_preparation_or_404(
        user=request.user, dataset=dataset, preparation_id=preparation_id
    )
    clone = rerun_preparation(actor=request.user, preparation=preparation)
    messages.success(request, _("A new immutable run was queued with the same source and recipe."))
    return _redirect_preparation(clone)


@login_required
def preparation_preview(
    request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug, preparation_id
):
    membership, project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    preparation = get_preparation_or_404(
        user=request.user, dataset=dataset, preparation_id=preparation_id
    )
    if preparation.status != DataPreparationStatus.READY:
        return _redirect_preparation(preparation)
    artifact = preparation.artifact
    page_size = 50
    page_obj = Paginator(range(artifact.row_count), page_size).get_page(request.GET.get("page"))
    headers, rows, offset = prepared_preview_page(
        preparation=preparation, page=page_obj.number, page_size=page_size
    )
    return render(
        request,
        "datasets/preparations/preview.html",
        _preparation_context(
            request,
            membership,
            project,
            dataset,
            preparation,
            artifact=artifact,
            headers=headers,
            rows=rows,
            offset=offset,
            page_obj=page_obj,
        ),
    )


@login_required
def preparation_download(
    request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug, preparation_id
):
    _membership, _project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    preparation = get_preparation_or_404(
        user=request.user, dataset=dataset, preparation_id=preparation_id
    )
    if not can_download_prepared_data(request.user, preparation):
        raise Http404
    if preparation.status != DataPreparationStatus.READY:
        raise Http404
    artifact = preparation.artifact
    storage = dataset_storage()
    if not storage.exists(artifact.storage_path):
        raise Http404
    filename = f"prepared-{dataset.slug}-{preparation.pk}.csv"
    return FileResponse(
        storage.open(artifact.storage_path, "rb"),
        as_attachment=True,
        filename=filename,
        content_type=artifact.media_type,
    )


@login_required
def preparation_delete(
    request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug, preparation_id
):
    membership, project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    preparation = get_preparation_or_404(
        user=request.user, dataset=dataset, preparation_id=preparation_id
    )
    if not can_delete_preparation(request.user, preparation):
        raise PermissionDenied
    form = DeletePreparationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            delete_preparation(actor=request.user, preparation=preparation)
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(request, _("Preparation and its prepared artifact were deleted. Original data was not changed."))
            return redirect(
                "datasets:preparation-list",
                workspace_slug=workspace_slug,
                project_id=project_id,
                project_slug=project_slug,
                dataset_id=dataset_id,
                dataset_slug=dataset_slug,
            )
    return render(
        request,
        "datasets/preparations/delete.html",
        _preparation_context(
            request,
            membership,
            project,
            dataset,
            preparation,
            form=form,
        ),
    )
