"""Transactional Project lifecycle operations and invariants."""

import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from workspaces.permissions import (
    can_archive_project,
    can_create_project,
    can_delete_project,
    can_duplicate_project,
    can_edit_project,
    can_restore_project,
)

from .models import Project, ProjectActivity, ProjectActivityEvent, ProjectStatus

logger = logging.getLogger(__name__)


def _unique_project_slug(workspace, name: str) -> str:
    base = slugify(name)[:150] or "project"
    candidate = base
    suffix = 2
    while Project.objects.filter(workspace=workspace, slug=candidate).exists():
        candidate = f"{base[:165]}-{suffix}"
        suffix += 1
        if suffix > 1000:
            raise ValidationError("Could not allocate a unique project slug.")
    return candidate


def _record_activity(project: Project, *, actor, event: str, detail: str = "") -> None:
    ProjectActivity.objects.create(
        project=project,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        event=event,
        detail=detail[:255],
    )


@transaction.atomic
def create_project(
    *,
    actor,
    workspace,
    name: str,
    description: str = "",
    domain: str = "",
    tags=None,
    notes: str = "",
) -> Project:
    """Create an active Project inside one explicitly authorised Workspace."""
    if not can_create_project(actor, workspace):
        raise PermissionDenied
    clean_name = name.strip()
    if not clean_name:
        raise ValidationError("Project name is required.")
    project = Project.objects.create(
        workspace=workspace,
        name=clean_name,
        slug=_unique_project_slug(workspace, clean_name),
        description=description.strip(),
        domain=domain.strip(),
        tags=list(tags or []),
        notes=notes.strip(),
        created_by=actor,
    )
    _record_activity(project, actor=actor, event=ProjectActivityEvent.CREATED)
    return project


@transaction.atomic
def update_project(
    *,
    actor,
    project: Project,
    name: str,
    description: str,
    domain: str,
    tags,
    notes: str,
) -> Project:
    """Update mutable metadata without changing the stable UUID or slug."""
    if not can_edit_project(actor, project):
        raise PermissionDenied
    locked = Project.objects.select_for_update().get(pk=project.pk)
    if locked.status == ProjectStatus.ARCHIVED:
        raise ValidationError("Restore the project before editing its metadata.")
    clean_name = name.strip()
    if not clean_name:
        raise ValidationError("Project name is required.")
    values = {
        "name": clean_name,
        "description": description.strip(),
        "domain": domain.strip(),
        "tags": list(tags or []),
        "notes": notes.strip(),
    }
    changed = [field for field, value in values.items() if getattr(locked, field) != value]
    for field, value in values.items():
        setattr(locked, field, value)
    if changed:
        locked.save(update_fields=(*changed, "updated_at"))
        _record_activity(
            locked,
            actor=actor,
            event=ProjectActivityEvent.UPDATED,
            detail=f"Updated: {', '.join(changed)}",
        )
    return locked


@transaction.atomic
def archive_project(*, actor, project: Project) -> Project:
    if not can_archive_project(actor, project):
        raise PermissionDenied
    locked = Project.objects.select_for_update().get(pk=project.pk)
    if locked.status == ProjectStatus.ARCHIVED:
        return locked
    locked.status = ProjectStatus.ARCHIVED
    locked.archived_at = timezone.now()
    locked.save(update_fields=("status", "archived_at", "updated_at"))
    _record_activity(locked, actor=actor, event=ProjectActivityEvent.ARCHIVED)
    return locked


@transaction.atomic
def restore_project(*, actor, project: Project) -> Project:
    if not can_restore_project(actor, project):
        raise PermissionDenied
    locked = Project.objects.select_for_update().get(pk=project.pk)
    if locked.status == ProjectStatus.ACTIVE:
        return locked
    locked.status = ProjectStatus.ACTIVE
    locked.archived_at = None
    locked.save(update_fields=("status", "archived_at", "updated_at"))
    _record_activity(locked, actor=actor, event=ProjectActivityEvent.RESTORED)
    return locked


@transaction.atomic
def duplicate_project(*, actor, project: Project) -> Project:
    """Duplicate only Plan 3 metadata into a new active Project."""
    if not can_duplicate_project(actor, project):
        raise PermissionDenied
    source = Project.objects.select_for_update().select_related("workspace").get(pk=project.pk)
    clone_name = f"{source.name} copy"
    clone = Project.objects.create(
        workspace=source.workspace,
        name=clone_name,
        slug=_unique_project_slug(source.workspace, clone_name),
        description=source.description,
        domain=source.domain,
        tags=list(source.tags or []),
        notes=source.notes,
        status=ProjectStatus.ACTIVE,
        archived_at=None,
        created_by=actor,
    )
    _record_activity(
        source,
        actor=actor,
        event=ProjectActivityEvent.DUPLICATED,
        detail=f"Duplicated as {clone.name}.",
    )
    _record_activity(
        clone,
        actor=actor,
        event=ProjectActivityEvent.DUPLICATED,
        detail=f"Duplicated from {source.name}.",
    )
    return clone


@transaction.atomic
def delete_project(*, actor, project: Project) -> None:
    """Permanently delete a Project after the caller has obtained explicit confirmation."""
    if not can_delete_project(actor, project):
        raise PermissionDenied
    locked = Project.objects.select_for_update().get(pk=project.pk)
    logger.info(
        "project.deleted project_id=%s workspace_id=%s actor_id=%s",
        locked.pk,
        locked.workspace_id,
        getattr(actor, "pk", None),
    )
    locked.delete()
