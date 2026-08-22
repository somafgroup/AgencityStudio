"""Server-rendered Data Workspace workflows with Project/Workspace-inherited permissions."""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from projects.models import Project
from workspaces.permissions import (
    can_add_dataset_version,
    can_annotate_dataset,
    can_confirm_dataset_version,
    can_create_dataset,
    can_delete_dataset,
    can_download_dataset,
    can_edit_dataset,
)
from workspaces.services import get_workspace_membership_or_404, workspace_memberships_for

from .forms import (
    DatasetForm,
    DatasetImportForm,
    DeleteDatasetForm,
    NewDatasetVersionForm,
    ReprocessDatasetVersionForm,
)
from .models import Dataset, DatasetColumnRole, DatasetImportStatus, DatasetVersion
from .services import (
    add_dataset_version_from_upload,
    confirm_dataset_version,
    create_dataset_from_paste,
    create_dataset_from_upload,
    delete_dataset,
    delete_failed_version,
    get_dataset_or_404,
    preview_page,
    reprocess_dataset_version,
    source_media_type,
    update_column_annotations,
    update_dataset,
)
from .storage import dataset_storage


def _current_membership(request):
    memberships = list(workspace_memberships_for(request.user))
    preferred_slug = request.session.get("current_workspace_slug")
    current = next((item for item in memberships if item.workspace.slug == preferred_slug), None)
    if current is None:
        current = next((item for item in memberships if item.workspace.is_personal), None)
    if current is None and memberships:
        current = memberships[0]
    if current is not None:
        request.session["current_workspace_slug"] = current.workspace.slug
    return current


def _membership_project(request, workspace_slug: str, project_id, project_slug: str):
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


def _membership_project_dataset(
    request,
    workspace_slug: str,
    project_id,
    project_slug: str,
    dataset_id,
    dataset_slug: str,
):
    membership, project = _membership_project(request, workspace_slug, project_id, project_slug)
    dataset = get_dataset_or_404(user=request.user, dataset_id=dataset_id, project=project)
    if dataset.slug != dataset_slug:
        raise Http404
    return membership, project, dataset


def _selected_version(request, dataset: Dataset) -> DatasetVersion | None:
    requested = request.GET.get("version")
    if requested:
        try:
            return DatasetVersion.objects.select_related("created_by", "confirmed_by").get(
                pk=requested,
                dataset=dataset,
            )
        except (DatasetVersion.DoesNotExist, ValueError) as exc:
            raise Http404 from exc
    if dataset.current_version_id:
        return DatasetVersion.objects.select_related("created_by", "confirmed_by").get(
            pk=dataset.current_version_id
        )
    return (
        DatasetVersion.objects.select_related("created_by", "confirmed_by")
        .filter(dataset=dataset)
        .order_by("-version_number")
        .first()
    )


def _dataset_context(
    request,
    membership,
    project,
    dataset: Dataset,
    *,
    active_section: str,
    version: DatasetVersion | None = None,
    **extra,
):
    version = version if version is not None else _selected_version(request, dataset)
    return {
        "active_nav": "datasets",
        "active_project_section": "datasets",
        "active_dataset_section": active_section,
        "page_title": dataset.name,
        "workspace": membership.workspace,
        "membership": membership,
        "project": project,
        "dataset": dataset,
        "version": version,
        "can_edit_dataset": can_edit_dataset(request.user, dataset),
        "can_add_dataset_version": can_add_dataset_version(request.user, dataset),
        "can_annotate_dataset": can_annotate_dataset(request.user, dataset),
        "can_confirm_dataset_version": can_confirm_dataset_version(request.user, dataset),
        "can_delete_dataset": can_delete_dataset(request.user, dataset),
        **extra,
    }


def _redirect_dataset(view_name: str, dataset: Dataset, **query):
    response = redirect(
        view_name,
        workspace_slug=dataset.project.workspace.slug,
        project_id=dataset.project_id,
        project_slug=dataset.project.slug,
        dataset_id=dataset.pk,
        dataset_slug=dataset.slug,
    )
    if query:
        response["Location"] += "?" + "&".join(f"{key}={value}" for key, value in query.items())
    return response


def _issue_message(issue: dict, columns: dict[int, str]) -> str:
    details = issue.get("details", {})
    position = issue.get("column_position")
    column = columns.get(position, _("the selected column"))
    code = issue.get("code")
    if code == "MISSING_VALUES":
        return _("%(column)s contains %(count)s missing values.") % {
            "column": column,
            "count": details.get("count", 0),
        }
    if code == "INFINITE_VALUES":
        return _("%(column)s contains %(count)s non-finite numeric values.") % {
            "column": column,
            "count": details.get("count", 0),
        }
    if code == "NON_NUMERIC_VALUES":
        return _("Observable %(column)s contains %(count)s non-numeric values.") % {
            "column": column,
            "count": details.get("count", 0),
        }
    if code == "TIME_DUPLICATE":
        return _("Time column %(column)s contains %(count)s duplicate timestamps.") % {
            "column": column,
            "count": details.get("count", 0),
        }
    if code == "TIME_NON_MONOTONIC":
        return _("Time column %(column)s is not strictly increasing.") % {"column": column}
    if code == "IRREGULAR_SAMPLING":
        return _("Sampling intervals in %(column)s are irregular.") % {"column": column}
    if code == "POTENTIAL_SAMPLING_GAP":
        return _("Potential sampling gap detected in %(column)s (inspection heuristic).") % {
            "column": column
        }
    if code == "TIME_UNREADABLE":
        return _("Time column %(column)s contains values that cannot be interpreted as time.") % {
            "column": column
        }
    if code == "TIME_MIXED_REPRESENTATION":
        return _("Time column %(column)s mixes incompatible time representations.") % {
            "column": column
        }
    if code == "DUPLICATE_HEADER":
        return _("The source contains duplicate column headers.")
    if code == "ROW_WIDTH_MISMATCH":
        return _("Some rows contain a different number of columns.")
    if code == "FORMULA_CELLS":
        return _("The XLSX source contains formula cells. Studio preserves formula text and does not execute it.")
    return str(code or _("Dataset inspection finding"))


def _present_issues(version: DatasetVersion) -> list[dict]:
    columns = {column.position: column.display_name for column in version.columns.all()}
    return [
        {**issue, "message": _issue_message(issue, columns)} for issue in version.quality_issues or []
    ]


@login_required
def dataset_list(request):
    membership = _current_membership(request)
    if membership is None:
        raise Http404
    datasets = (
        Dataset.objects.for_workspace(membership.workspace)
        .select_related("project", "project__workspace", "current_version", "created_by")
        .order_by("-updated_at")
    )
    query = request.GET.get("q", "").strip()
    if query:
        datasets = datasets.filter(
            Q(name__icontains=query)
            | Q(project__name__icontains=query)
            | Q(versions__original_filename__icontains=query)
        ).distinct()
    sort = request.GET.get("sort", "updated")
    ordering = {
        "name": ("name",),
        "created": ("-created_at",),
        "updated": ("-updated_at",),
    }.get(sort, ("-updated_at",))
    page_obj = Paginator(datasets.order_by(*ordering), 20).get_page(request.GET.get("page"))
    return render(
        request,
        "datasets/list.html",
        {
            "active_nav": "datasets",
            "page_title": _("Datasets"),
            "workspace": membership.workspace,
            "membership": membership,
            "page_obj": page_obj,
            "query": query,
            "sort": sort,
        },
    )


@login_required
def project_datasets(request, workspace_slug: str, project_id, project_slug: str):
    membership, project = _membership_project(request, workspace_slug, project_id, project_slug)
    datasets = project.datasets.select_related("current_version", "created_by").order_by("-updated_at")
    page_obj = Paginator(datasets, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "datasets/project_list.html",
        {
            "active_nav": "projects",
            "active_project_section": "datasets",
            "page_title": _("Datasets"),
            "workspace": membership.workspace,
            "membership": membership,
            "project": project,
            "page_obj": page_obj,
            "can_create_dataset": can_create_dataset(request.user, project),
        },
    )


@login_required
def dataset_import(request, workspace_slug: str, project_id, project_slug: str):
    membership, project = _membership_project(request, workspace_slug, project_id, project_slug)
    if not can_create_dataset(request.user, project):
        raise PermissionDenied
    form = DatasetImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            if form.cleaned_data["source_mode"] == DatasetImportForm.SOURCE_PASTE:
                dataset, version = create_dataset_from_paste(
                    actor=request.user,
                    project=project,
                    name=form.cleaned_data["name"],
                    description=form.cleaned_data["description"],
                    source_text=form.cleaned_data["pasted_data"],
                    import_options=form.import_options(),
                )
            else:
                dataset, version = create_dataset_from_upload(
                    actor=request.user,
                    project=project,
                    name=form.cleaned_data["name"],
                    description=form.cleaned_data["description"],
                    uploaded_file=form.cleaned_data["source_file"],
                    import_options=form.import_options(),
                )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            messages.success(request, _("Source stored exactly as uploaded. Inspection has started."))
            return _redirect_dataset("datasets:overview", dataset, version=version.pk)
    return render(
        request,
        "datasets/import.html",
        {
            "active_nav": "datasets",
            "active_project_section": "datasets",
            "page_title": _("Import dataset"),
            "workspace": membership.workspace,
            "membership": membership,
            "project": project,
            "form": form,
            "max_upload_bytes": settings.DATASET_MAX_UPLOAD_BYTES,
        },
    )


@login_required
def dataset_overview(
    request, workspace_slug: str, project_id, project_slug: str, dataset_id, dataset_slug: str
):
    membership, project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    version = _selected_version(request, dataset)
    return render(
        request,
        "datasets/overview.html",
        _dataset_context(
            request,
            membership,
            project,
            dataset,
            active_section="overview",
            version=version,
            issues=_present_issues(version) if version else [],
        ),
    )


@login_required
def dataset_status(
    request, workspace_slug: str, project_id, project_slug: str, dataset_id, dataset_slug: str
):
    membership, project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    version = _selected_version(request, dataset)
    return render(
        request,
        "datasets/_status.html",
        _dataset_context(
            request,
            membership,
            project,
            dataset,
            active_section="overview",
            version=version,
        ),
    )


@login_required
def dataset_preview(
    request, workspace_slug: str, project_id, project_slug: str, dataset_id, dataset_slug: str
):
    membership, project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    version = _selected_version(request, dataset)
    headers: list[str] = []
    rows: list[list[object]] = []
    page_obj = None
    offset = 0
    if version and version.import_status == DatasetImportStatus.READY:
        page_size = max(1, min(settings.DATASET_PREVIEW_PAGE_SIZE, 200))
        paginator = Paginator(range(version.row_count or 0), page_size)
        page_obj = paginator.get_page(request.GET.get("page"))
        headers, rows, offset = preview_page(
            version=version,
            page=page_obj.number,
            page_size=page_size,
        )
    return render(
        request,
        "datasets/preview.html",
        _dataset_context(
            request,
            membership,
            project,
            dataset,
            active_section="preview",
            version=version,
            headers=headers,
            rows=rows,
            page_obj=page_obj,
            offset=offset,
        ),
    )


@login_required
def dataset_columns(
    request, workspace_slug: str, project_id, project_slug: str, dataset_id, dataset_slug: str
):
    membership, project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    version = _selected_version(request, dataset)
    if version is None:
        raise Http404
    if request.method == "POST":
        if not can_annotate_dataset(request.user, dataset):
            raise PermissionDenied
        annotations = {}
        for column in version.columns.all():
            annotations[column.position] = {
                "role": request.POST.get(f"role_{column.position}", DatasetColumnRole.OTHER),
                "unit": request.POST.get(f"unit_{column.position}", ""),
            }
        try:
            update_column_annotations(actor=request.user, version=version, annotations=annotations)
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(request, _("Column annotations saved. Quality inspection is refreshing."))
            return _redirect_dataset("datasets:columns", dataset, version=version.pk)
    version = DatasetVersion.objects.prefetch_related("columns").get(pk=version.pk)
    return render(
        request,
        "datasets/columns.html",
        _dataset_context(
            request,
            membership,
            project,
            dataset,
            active_section="columns",
            version=version,
            columns=version.columns.all(),
            column_roles=DatasetColumnRole.choices,
        ),
    )


@login_required
def dataset_quality(
    request, workspace_slug: str, project_id, project_slug: str, dataset_id, dataset_slug: str
):
    membership, project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    version = _selected_version(request, dataset)
    return render(
        request,
        "datasets/quality.html",
        _dataset_context(
            request,
            membership,
            project,
            dataset,
            active_section="quality",
            version=version,
            issues=_present_issues(version) if version else [],
        ),
    )


@login_required
def dataset_versions(
    request, workspace_slug: str, project_id, project_slug: str, dataset_id, dataset_slug: str
):
    membership, project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    versions = dataset.versions.select_related("created_by", "confirmed_by").all()
    return render(
        request,
        "datasets/versions.html",
        _dataset_context(
            request,
            membership,
            project,
            dataset,
            active_section="versions",
            versions=versions,
        ),
    )


@login_required
def dataset_source(
    request, workspace_slug: str, project_id, project_slug: str, dataset_id, dataset_slug: str
):
    membership, project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    version = _selected_version(request, dataset)
    reprocess_form = None
    if version and can_annotate_dataset(request.user, dataset):
        options = version.import_options or {}
        initial = {
            "encoding": options.get("encoding", ""),
            "delimiter": options.get("delimiter", ""),
            "header_mode": (
                "yes" if options.get("has_header") is True else "no" if options.get("has_header") is False else ""
            ),
            "decimal_separator": options.get("decimal_separator", "."),
            "sheet": options.get("sheet", ""),
        }
        reprocess_form = ReprocessDatasetVersionForm(initial=initial)
    return render(
        request,
        "datasets/source.html",
        _dataset_context(
            request,
            membership,
            project,
            dataset,
            active_section="source",
            version=version,
            reprocess_form=reprocess_form,
        ),
    )


@login_required
def dataset_settings(
    request, workspace_slug: str, project_id, project_slug: str, dataset_id, dataset_slug: str
):
    membership, project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    if not can_edit_dataset(request.user, dataset):
        raise PermissionDenied
    form = DatasetForm(request.POST or None, instance=dataset)
    if request.method == "POST" and form.is_valid():
        try:
            update_dataset(
                actor=request.user,
                dataset=dataset,
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            messages.success(request, _("Dataset metadata updated."))
            return _redirect_dataset("datasets:settings", dataset)
    return render(
        request,
        "datasets/settings.html",
        _dataset_context(
            request,
            membership,
            project,
            dataset,
            active_section="settings",
            form=form,
        ),
    )


@login_required
def dataset_new_version(
    request, workspace_slug: str, project_id, project_slug: str, dataset_id, dataset_slug: str
):
    membership, project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    if not can_add_dataset_version(request.user, dataset):
        raise PermissionDenied
    form = NewDatasetVersionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            version = add_dataset_version_from_upload(
                actor=request.user,
                dataset=dataset,
                uploaded_file=form.cleaned_data["source_file"],
                import_options=form.import_options(),
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            messages.success(request, _("New source version stored. Inspection has started."))
            return _redirect_dataset("datasets:overview", dataset, version=version.pk)
    return render(
        request,
        "datasets/new_version.html",
        _dataset_context(
            request,
            membership,
            project,
            dataset,
            active_section="versions",
            form=form,
        ),
    )


@login_required
def dataset_reprocess(
    request,
    workspace_slug: str,
    project_id,
    project_slug: str,
    dataset_id,
    dataset_slug: str,
    version_id,
):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    _membership, _project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    if not can_annotate_dataset(request.user, dataset):
        raise PermissionDenied
    try:
        version = dataset.versions.get(pk=version_id)
    except DatasetVersion.DoesNotExist as exc:
        raise Http404 from exc
    form = ReprocessDatasetVersionForm(request.POST)
    if form.is_valid():
        try:
            reprocess_dataset_version(
                actor=request.user,
                version=version,
                import_options=form.import_options(),
            )
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(request, _("Dataset inspection restarted with the selected options."))
    else:
        messages.error(request, _("Review the import settings and try again."))
    return _redirect_dataset("datasets:source", dataset, version=version.pk)


@login_required
def dataset_confirm(
    request,
    workspace_slug: str,
    project_id,
    project_slug: str,
    dataset_id,
    dataset_slug: str,
    version_id,
):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    _membership, _project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    if not can_confirm_dataset_version(request.user, dataset):
        raise PermissionDenied
    try:
        version = dataset.versions.get(pk=version_id)
        confirm_dataset_version(actor=request.user, version=version)
    except DatasetVersion.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        messages.error(request, exc.message)
    else:
        messages.success(request, _("Dataset version confirmed as current."))
    return _redirect_dataset("datasets:overview", dataset, version=version_id)


@login_required
def dataset_download(
    request,
    workspace_slug: str,
    project_id,
    project_slug: str,
    dataset_id,
    dataset_slug: str,
    version_id,
):
    _membership, _project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    if not can_download_dataset(request.user, dataset):
        raise Http404
    try:
        version = dataset.versions.get(pk=version_id)
    except DatasetVersion.DoesNotExist as exc:
        raise Http404 from exc
    storage = dataset_storage()
    if not storage.exists(version.source_path):
        raise Http404
    return FileResponse(
        storage.open(version.source_path, "rb"),
        as_attachment=True,
        filename=version.original_filename,
        content_type=source_media_type(version),
    )


@login_required
def dataset_delete(
    request, workspace_slug: str, project_id, project_slug: str, dataset_id, dataset_slug: str
):
    membership, project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    if not can_delete_dataset(request.user, dataset):
        raise PermissionDenied
    form = DeleteDatasetForm(request.POST or None, dataset_name=dataset.name)
    if request.method == "POST" and form.is_valid():
        delete_dataset(actor=request.user, dataset=dataset)
        messages.success(request, _("Dataset permanently deleted."))
        return redirect(
            "datasets:project-list",
            workspace_slug=project.workspace.slug,
            project_id=project.pk,
            project_slug=project.slug,
        )
    return render(
        request,
        "datasets/delete.html",
        _dataset_context(
            request,
            membership,
            project,
            dataset,
            active_section="settings",
            form=form,
        ),
    )


@login_required
def failed_version_delete(
    request,
    workspace_slug: str,
    project_id,
    project_slug: str,
    dataset_id,
    dataset_slug: str,
    version_id,
):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    _membership, _project, dataset = _membership_project_dataset(
        request, workspace_slug, project_id, project_slug, dataset_id, dataset_slug
    )
    try:
        version = dataset.versions.get(pk=version_id)
        delete_failed_version(actor=request.user, version=version)
    except DatasetVersion.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        messages.error(request, exc.message)
    else:
        messages.success(request, _("Failed dataset version removed."))
    return _redirect_dataset("datasets:versions", dataset)
