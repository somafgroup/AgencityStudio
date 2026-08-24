"""Transactional lifecycle services for System identities and immutable revisions."""

from __future__ import annotations

import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.http import Http404
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _

from projects.models import ProjectActivity, ProjectActivityEvent, ProjectStatus
from workspaces.permissions import (
    can_archive_system,
    can_create_system,
    can_delete_system,
    can_duplicate_system,
    can_edit_system_identity,
    can_restore_system,
    can_revise_system,
    can_view_system,
)

from .models import (
    ObservableDefinition,
    ScientificReference,
    System,
    SystemRevision,
    SystemStatus,
)
from .serialization import configuration_fingerprint
from .validation import documented_context_is_complete, validate_revision_context

logger = logging.getLogger(__name__)


def _record(system: System, *, actor, event: str, detail: str = "") -> None:
    ProjectActivity.objects.create(
        project=system.project,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        event=event,
        detail=detail[:255],
    )


def _clean_system_name(name: str) -> str:
    clean = str(name).strip()
    if not clean:
        raise ValidationError(_("System name is required."))
    if len(clean) > 180:
        raise ValidationError(_("System name must be 180 characters or fewer."))
    return clean


def _derived_name(template: str, source_name: str) -> str:
    return _clean_system_name((template % {"name": source_name})[:180])


def _unique_slug(project, name: str) -> str:
    base = slugify(name)[:150] or "system"
    candidate = base
    suffix = 2
    while System.objects.filter(project=project, slug=candidate).exists():
        candidate = f"{base[:165]}-{suffix}"
        suffix += 1
        if suffix > 1000:
            raise ValidationError(_("Could not allocate a unique system slug."))
    return candidate


def get_system_or_404(*, user, project, system_id, system_slug: str) -> System:
    try:
        system = (
            System.objects.select_related(
                "project",
                "project__workspace",
                "created_by",
                "current_revision",
            )
            .prefetch_related(
                "current_revision__observables",
                "current_revision__references",
            )
            .get(pk=system_id, project=project, slug=system_slug)
        )
    except (System.DoesNotExist, ValueError) as exc:
        raise Http404 from exc
    if not can_view_system(user, system):
        raise Http404
    return system


def _normalise_observables(observables: list[dict]) -> list[dict]:
    clean: list[dict] = []
    for item in observables:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        clean.append(
            {
                "name": name[:180],
                "symbol": str(item.get("symbol", "")).strip()[:80],
                "description": str(item.get("description", "")).strip(),
                "unit": str(item.get("unit", "")).strip()[:80],
                "observable_kind": str(item.get("observable_kind", "")).strip()[:120],
                "nature": item.get("nature"),
                "source_description": str(item.get("source_description", "")).strip(),
                "is_primary": bool(item.get("is_primary")),
            }
        )
    if clean and not any(item["is_primary"] for item in clean):
        clean[0]["is_primary"] = True
    return clean


def _normalise_references(references: list[dict]) -> list[dict]:
    clean: list[dict] = []
    for item in references:
        citation = str(item.get("citation", "")).strip()
        title = str(item.get("title", "")).strip()
        if not citation and not title:
            continue
        clean.append(
            {
                "title": title[:255],
                "citation": citation or title,
                "doi": str(item.get("doi", "")).strip()[:255],
                "url": str(item.get("url", "")).strip()[:500],
                "notes": str(item.get("notes", "")).strip(),
                "supports_a_ref": bool(item.get("supports_a_ref")),
                "supports_tau": bool(item.get("supports_tau")),
                "supports_w": bool(item.get("supports_w")),
                "supports_p_c": bool(item.get("supports_p_c")),
            }
        )
    return clean


def _create_revision(
    *,
    actor,
    locked_system: System,
    data: dict,
    observables: list[dict],
    references: list[dict],
) -> SystemRevision:
    observables = _normalise_observables(observables)
    references = _normalise_references(references)
    parsed, issues = validate_revision_context(data, observables)
    if data.get("documentation_status") == "DOCUMENTED" and not documented_context_is_complete(
        issues
    ):
        raise ValidationError(
            [issue.message for issue in issues if issue.code.startswith("MISSING_")]
        )

    number = (
        SystemRevision.objects.filter(system=locked_system).aggregate(value=Max("revision_number"))[
            "value"
        ]
        or 0
    ) + 1
    revision_fields = {
        key: parsed.get(key)
        for key in (
            "documentation_status",
            "description",
            "domain",
            "system_type",
            "mechanism",
            "environment",
            "measurement_context",
            "scientific_notes",
            "revision_reason",
            "a_ref_value",
            "a_ref_value_text",
            "a_ref_unit",
            "a_ref_origin",
            "a_ref_origin_detail",
            "a_ref_justification",
            "tau_value",
            "tau_value_text",
            "tau_unit",
            "tau_origin",
            "tau_origin_detail",
            "tau_justification",
            "w_mode",
            "w_value",
            "w_value_text",
            "w_unit",
            "w_origin",
            "w_origin_detail",
            "w_justification",
            "p_c_mode",
            "p_c_value",
            "p_c_value_text",
            "p_c_unit",
            "p_c_origin",
            "p_c_origin_detail",
            "p_c_justification",
        )
    }
    revision = SystemRevision.objects.create(
        system=locked_system,
        revision_number=number,
        created_by=actor,
        **revision_fields,
    )
    ObservableDefinition.objects.bulk_create(
        [
            ObservableDefinition(revision=revision, position=index, **observable)
            for index, observable in enumerate(observables, 1)
        ]
    )
    ScientificReference.objects.bulk_create(
        [ScientificReference(revision=revision, **reference) for reference in references]
    )
    fingerprint = configuration_fingerprint(revision)
    SystemRevision.objects.filter(pk=revision.pk).update(configuration_fingerprint=fingerprint)
    System.objects.filter(pk=locked_system.pk).update(
        current_revision=revision,
        updated_at=timezone.now(),
    )
    revision.configuration_fingerprint = fingerprint
    locked_system.current_revision = revision
    return revision


@transaction.atomic
def create_system(
    *,
    actor,
    project,
    name: str,
    description: str,
    revision_data: dict,
    observables: list[dict],
    references: list[dict],
) -> System:
    """Create a stable System identity and its first scientific revision atomically."""
    if not can_create_system(actor, project):
        raise PermissionDenied
    if project.status != ProjectStatus.ACTIVE:
        raise ValidationError(_("Restore the project before defining a system."))
    clean_name = _clean_system_name(name)
    system = System.objects.create(
        project=project,
        name=clean_name,
        slug=_unique_slug(project, clean_name),
        description=str(description).strip(),
        created_by=actor,
    )
    locked = System.objects.select_for_update().get(pk=system.pk)
    _create_revision(
        actor=actor,
        locked_system=locked,
        data=revision_data,
        observables=observables,
        references=references,
    )
    system.refresh_from_db()
    _record(system, actor=actor, event=ProjectActivityEvent.SYS_CREATED)
    return system


@transaction.atomic
def create_system_revision(
    *,
    actor,
    system: System,
    revision_data: dict,
    observables: list[dict],
    references: list[dict],
) -> SystemRevision:
    if not can_revise_system(actor, system):
        raise PermissionDenied
    locked = System.objects.select_for_update().select_related("project").get(pk=system.pk)
    if locked.status != SystemStatus.ACTIVE or locked.project.status != ProjectStatus.ACTIVE:
        raise ValidationError(_("Restore the project and system before creating a revision."))
    revision = _create_revision(
        actor=actor,
        locked_system=locked,
        data=revision_data,
        observables=observables,
        references=references,
    )
    _record(
        locked,
        actor=actor,
        event=ProjectActivityEvent.SYS_REVISED,
        detail=_("Created scientific Revision %(revision)s.")
        % {"revision": revision.revision_number},
    )
    return revision


@transaction.atomic
def update_system_identity(*, actor, system: System, name: str, description: str) -> System:
    if not can_edit_system_identity(actor, system):
        raise PermissionDenied
    locked = System.objects.select_for_update().get(pk=system.pk)
    if locked.status != SystemStatus.ACTIVE:
        raise ValidationError(_("Restore the system before editing organisational metadata."))
    locked.name = _clean_system_name(name)
    locked.description = str(description).strip()
    locked.save(update_fields=("name", "description", "updated_at"))
    return locked


@transaction.atomic
def duplicate_system(*, actor, system: System) -> System:
    if not can_duplicate_system(actor, system):
        raise PermissionDenied
    source = (
        System.objects.select_for_update()
        .select_related("project")
        .get(pk=system.pk)
    )
    if source.current_revision_id is None:
        raise ValidationError(_("The source system has no scientific revision to duplicate."))
    current = (
        SystemRevision.objects.prefetch_related("observables", "references")
        .get(pk=source.current_revision_id, system=source)
    )
    clone_name = _derived_name(_("Copy of %(name)s"), source.name)
    clone = System.objects.create(
        project=source.project,
        name=clone_name,
        slug=_unique_slug(source.project, clone_name),
        description=source.description,
        duplicated_from=source,
        created_by=actor,
    )
    revision_data = {
        field: getattr(current, field)
        for field in (
            "documentation_status",
            "description",
            "domain",
            "system_type",
            "mechanism",
            "environment",
            "measurement_context",
            "scientific_notes",
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
    }
    revision_data["revision_reason"] = _("Duplicated from %(name)s.") % {
        "name": source.name
    }
    observables = [
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
        for item in current.observables.all()
    ]
    references = [
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
        for item in current.references.all()
    ]
    locked_clone = System.objects.select_for_update().get(pk=clone.pk)
    _create_revision(
        actor=actor,
        locked_system=locked_clone,
        data=revision_data,
        observables=observables,
        references=references,
    )
    clone.refresh_from_db()
    _record(
        source,
        actor=actor,
        event=ProjectActivityEvent.SYS_DUPLICATED,
        detail=_("Duplicated as %(name)s.") % {"name": clone.name},
    )
    _record(
        clone,
        actor=actor,
        event=ProjectActivityEvent.SYS_DUPLICATED,
        detail=_("Duplicated from %(name)s.") % {"name": source.name},
    )
    return clone


@transaction.atomic
def archive_system(*, actor, system: System) -> System:
    if not can_archive_system(actor, system):
        raise PermissionDenied
    locked = System.objects.select_for_update().get(pk=system.pk)
    if locked.status == SystemStatus.ARCHIVED:
        return locked
    locked.status = SystemStatus.ARCHIVED
    locked.archived_at = timezone.now()
    locked.save(update_fields=("status", "archived_at", "updated_at"))
    _record(locked, actor=actor, event=ProjectActivityEvent.SYS_ARCHIVED)
    return locked


@transaction.atomic
def restore_system(*, actor, system: System) -> System:
    if not can_restore_system(actor, system):
        raise PermissionDenied
    locked = System.objects.select_for_update().get(pk=system.pk)
    if locked.status == SystemStatus.ACTIVE:
        return locked
    locked.status = SystemStatus.ACTIVE
    locked.archived_at = None
    locked.save(update_fields=("status", "archived_at", "updated_at"))
    _record(locked, actor=actor, event=ProjectActivityEvent.SYS_RESTORED)
    return locked


@transaction.atomic
def delete_system(*, actor, system: System) -> None:
    if not can_delete_system(actor, system):
        raise PermissionDenied
    locked = System.objects.select_for_update().get(pk=system.pk)
    project = locked.project
    system_id = locked.pk
    locked.delete()
    ProjectActivity.objects.create(
        project=project,
        actor=actor,
        event=ProjectActivityEvent.SYS_DELETED,
        detail=_("Deleted System %(id)s.") % {"id": system_id},
    )
    logger.info(
        "system.deleted system_id=%s project_id=%s actor_id=%s",
        system_id,
        project.pk,
        getattr(actor, "pk", None),
    )
