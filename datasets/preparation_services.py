"""Transactional lifecycle services for explicit DataPreparation recipes and artifacts."""

from __future__ import annotations

import platform
import uuid
from importlib.metadata import PackageNotFoundError, version as package_version

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from django.utils.translation import gettext as _

from projects.models import ProjectActivity, ProjectActivityEvent
from workspaces.permissions import (
    can_create_preparation,
    can_delete_preparation,
    can_download_prepared_data,
    can_duplicate_preparation,
    can_edit_preparation,
    can_run_preparation,
    can_view_preparation,
)

from .importers import get_importer
from .models import (
    DataPreparation,
    DataPreparationStatus,
    DatasetImportStatus,
    DatasetSourceFormat,
    DatasetVersion,
)
from .preparation import (
    ENGINE_ID,
    ENGINE_VERSION,
    PreparationError,
    normalise_step,
    recipe_fingerprint,
    validate_recipe_metadata,
)
from .storage import dataset_storage


def _distribution_version(name: str) -> str:
    try:
        return package_version(name)
    except PackageNotFoundError:
        return "not-installed"


def preparation_software_context() -> dict:
    """Return software provenance for Studio-owned preparation execution."""
    return {
        "studio_version": _distribution_version("agencitystudio"),
        "python_version": platform.python_version(),
        "engine_id": ENGINE_ID,
        "engine_version": ENGINE_VERSION,
        "dependencies": {
            "numpy": _distribution_version("numpy"),
            "Pint": _distribution_version("Pint"),
        },
    }


def _record(preparation: DataPreparation, *, actor, event: str, detail: str) -> None:
    ProjectActivity.objects.create(
        project=preparation.source_version.dataset.project,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        event=event,
        detail=detail[:255],
    )


def _source_column_contracts(version: DatasetVersion) -> list[dict]:
    return [
        {
            "position": column.position,
            "source_position": column.position,
            "source_name": column.source_name,
            "display_name": column.display_name,
            "role": column.role,
            "unit": column.unit,
            "inferred_type": column.inferred_type,
        }
        for column in version.columns.order_by("position")
    ]


def _clean_name(name: str) -> str:
    clean = str(name).strip()
    if not clean:
        raise ValidationError(_("Preparation name is required."))
    if len(clean) > 180:
        raise ValidationError(_("Preparation name must be 180 characters or fewer."))
    return clean


def _locked_preparation(preparation_id) -> DataPreparation:
    return (
        DataPreparation.objects.select_for_update()
        .select_related(
            "source_version",
            "source_version__dataset",
            "source_version__dataset__project",
            "source_version__dataset__project__workspace",
        )
        .get(pk=preparation_id)
    )


def _enqueue_preparation(preparation_id) -> None:
    from .preparation_tasks import execute_data_preparation

    execute_data_preparation.delay(str(preparation_id))


def create_preparation(
    *,
    actor,
    source_version: DatasetVersion,
    name: str,
    description: str = "",
) -> DataPreparation:
    """Create an editable draft pinned to one exact inspected original source version."""
    source_version = (
        DatasetVersion.objects.select_related("dataset", "dataset__project", "dataset__project__workspace")
        .prefetch_related("columns")
        .get(pk=source_version.pk)
    )
    if not can_create_preparation(actor, source_version.dataset):
        raise PermissionDenied
    if source_version.import_status != DatasetImportStatus.READY:
        raise ValidationError(_("Only a successfully inspected dataset version can be prepared."))
    clean_name = _clean_name(name)
    preparation = DataPreparation.objects.create(
        source_version=source_version,
        name=clean_name,
        description=str(description).strip(),
        recipe=[],
        recipe_hash=recipe_fingerprint(source_version.source_sha256, []),
        created_by=actor,
    )
    _record(
        preparation,
        actor=actor,
        event=ProjectActivityEvent.PREP_CREATED,
        detail=_("Created preparation %(name)s from Dataset v%(version)s.")
        % {"name": preparation.name, "version": source_version.version_number},
    )
    return preparation


def get_preparation_or_404(*, user, dataset, preparation_id) -> DataPreparation:
    try:
        preparation = (
            DataPreparation.objects.select_related(
                "source_version",
                "source_version__dataset",
                "source_version__dataset__project",
                "source_version__dataset__project__workspace",
                "created_by",
            )
            .filter(source_version__dataset=dataset)
            .get(pk=preparation_id)
        )
    except (DataPreparation.DoesNotExist, ValueError) as exc:
        raise Http404 from exc
    if not can_view_preparation(user, preparation):
        raise Http404
    return preparation


def preparation_artifact_path(preparation: DataPreparation, artifact_id) -> str:
    dataset = preparation.source_version.dataset
    return (
        f"datasets/{dataset.project_id}/{dataset.pk}/{preparation.source_version_id}/"
        f"prepared/{preparation.pk}/{artifact_id}/data.csv"
    )


@transaction.atomic
def add_preparation_step(*, actor, preparation: DataPreparation, step: dict) -> DataPreparation:
    locked = _locked_preparation(preparation.pk)
    if not can_edit_preparation(actor, locked):
        raise PermissionDenied
    clean_step = normalise_step(step)
    recipe = [*locked.recipe, clean_step]
    try:
        recipe = validate_recipe_metadata(recipe, _source_column_contracts(locked.source_version))
    except PreparationError as exc:
        raise ValidationError(str(exc)) from exc
    locked.recipe = recipe
    locked.recipe_hash = recipe_fingerprint(locked.source_version.source_sha256, recipe)
    locked.save(update_fields=("recipe", "recipe_hash", "updated_at"))
    return locked


@transaction.atomic
def remove_preparation_step(*, actor, preparation: DataPreparation, index: int) -> DataPreparation:
    locked = _locked_preparation(preparation.pk)
    if not can_edit_preparation(actor, locked):
        raise PermissionDenied
    if index < 0 or index >= len(locked.recipe):
        raise ValidationError(_("The selected preparation step no longer exists."))
    recipe = list(locked.recipe)
    recipe.pop(index)
    locked.recipe = recipe
    locked.recipe_hash = recipe_fingerprint(locked.source_version.source_sha256, recipe)
    locked.save(update_fields=("recipe", "recipe_hash", "updated_at"))
    return locked


@transaction.atomic
def move_preparation_step(
    *, actor, preparation: DataPreparation, index: int, direction: str
) -> DataPreparation:
    locked = _locked_preparation(preparation.pk)
    if not can_edit_preparation(actor, locked):
        raise PermissionDenied
    if index < 0 or index >= len(locked.recipe):
        raise ValidationError(_("The selected preparation step no longer exists."))
    destination = index - 1 if direction == "up" else index + 1 if direction == "down" else index
    if destination < 0 or destination >= len(locked.recipe) or destination == index:
        return locked
    recipe = list(locked.recipe)
    recipe[index], recipe[destination] = recipe[destination], recipe[index]
    try:
        recipe = validate_recipe_metadata(recipe, _source_column_contracts(locked.source_version))
    except PreparationError as exc:
        raise ValidationError(str(exc)) from exc
    locked.recipe = recipe
    locked.recipe_hash = recipe_fingerprint(locked.source_version.source_sha256, recipe)
    locked.save(update_fields=("recipe", "recipe_hash", "updated_at"))
    return locked


@transaction.atomic
def run_preparation(*, actor, preparation: DataPreparation) -> DataPreparation:
    """Freeze a draft recipe and enqueue it only after the transaction commits."""
    locked = _locked_preparation(preparation.pk)
    if not can_run_preparation(actor, locked):
        raise PermissionDenied
    if not locked.recipe:
        raise ValidationError(_("Add at least one explicit transformation before running."))
    try:
        recipe = validate_recipe_metadata(
            list(locked.recipe), _source_column_contracts(locked.source_version)
        )
    except PreparationError as exc:
        raise ValidationError(str(exc)) from exc
    context = preparation_software_context()
    locked.recipe = recipe
    locked.recipe_hash = recipe_fingerprint(locked.source_version.source_sha256, recipe)
    locked.status = DataPreparationStatus.QUEUED
    locked.engine_id = context["engine_id"]
    locked.engine_version = context["engine_version"]
    locked.studio_version = context["studio_version"]
    locked.python_version = context["python_version"]
    locked.dependency_versions = context["dependencies"]
    locked.failure_summary = ""
    locked.warnings = []
    locked.queued_at = timezone.now()
    locked.save(
        update_fields=(
            "recipe",
            "recipe_hash",
            "status",
            "engine_id",
            "engine_version",
            "studio_version",
            "python_version",
            "dependency_versions",
            "failure_summary",
            "warnings",
            "queued_at",
            "updated_at",
        )
    )
    transaction.on_commit(lambda: _enqueue_preparation(locked.pk))
    return locked


@transaction.atomic
def duplicate_preparation(*, actor, preparation: DataPreparation) -> DataPreparation:
    source = _locked_preparation(preparation.pk)
    if not can_duplicate_preparation(actor, source):
        raise PermissionDenied
    clone = DataPreparation.objects.create(
        source_version=source.source_version,
        name=_clean_name(_("Copy of %(name)s") % {"name": source.name}),
        description=source.description,
        recipe=list(source.recipe),
        recipe_hash=recipe_fingerprint(source.source_version.source_sha256, list(source.recipe)),
        created_by=actor,
    )
    _record(
        clone,
        actor=actor,
        event=ProjectActivityEvent.PREP_DUPLICATED,
        detail=_("Duplicated preparation %(name)s.") % {"name": source.name},
    )
    return clone


def rerun_preparation(*, actor, preparation: DataPreparation) -> DataPreparation:
    """Create a new immutable run record with the same source and ordered recipe."""
    clone = duplicate_preparation(actor=actor, preparation=preparation)
    clone.name = _clean_name(_("Re-run of %(name)s") % {"name": preparation.name})
    clone.save(update_fields=("name", "updated_at"))
    return run_preparation(actor=actor, preparation=clone)


@transaction.atomic
def delete_preparation(*, actor, preparation: DataPreparation) -> None:
    locked = _locked_preparation(preparation.pk)
    if not can_delete_preparation(actor, locked):
        raise PermissionDenied
    if locked.status in {DataPreparationStatus.QUEUED, DataPreparationStatus.PROCESSING}:
        raise ValidationError(_("A queued or processing preparation cannot be deleted."))
    artifact_path = None
    try:
        artifact_path = locked.artifact.storage_path
    except AttributeError:
        artifact_path = None
    _record(
        locked,
        actor=actor,
        event=ProjectActivityEvent.PREP_DELETED,
        detail=_("Deleted preparation %(name)s.") % {"name": locked.name},
    )
    locked.delete()
    if artifact_path:
        transaction.on_commit(lambda: dataset_storage().delete(artifact_path))


def prepared_preview_page(
    *, preparation: DataPreparation, page: int, page_size: int
) -> tuple[list[str], list[list[object]], int]:
    if preparation.status != DataPreparationStatus.READY:
        raise ValidationError(_("Prepared data is not ready yet."))
    try:
        artifact = preparation.artifact
    except AttributeError as exc:
        raise ValidationError(_("Prepared data artifact is unexpectedly missing.")) from exc
    page_size = max(1, min(int(page_size), 200))
    page = max(1, int(page))
    offset = (page - 1) * page_size
    importer = get_importer(DatasetSourceFormat.CSV)
    with dataset_storage().open(artifact.storage_path, "rb") as handle:
        headers, rows = importer.read_page(
            handle,
            filename="prepared.csv",
            options={
                "encoding": "utf-8",
                "delimiter": ",",
                "has_header": True,
                "decimal_separator": ".",
            },
            offset=offset,
            limit=page_size,
        )
    return headers, rows, offset


def can_download_result(user, preparation: DataPreparation) -> bool:
    return can_download_prepared_data(user, preparation)
