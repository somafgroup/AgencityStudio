import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse

from labbridge.scientific_context import inspect_public_context_contract
from labbridge.service import SUPPORTED_AGENCITYLAB_VERSION
from projects.services import create_project, delete_project
from systems.models import (
    MemoryWindowMode,
    ObservableDefinition,
    RevisionDocumentationStatus,
    System,
)
from systems.serialization import configuration_fingerprint
from systems.services import (
    archive_system,
    create_system,
    create_system_revision,
    duplicate_system,
    restore_system,
)
from systems.validation import validate_revision_context
from workspaces.models import WorkspaceMembership, WorkspaceRole
from workspaces.permissions import (
    can_create_system,
    can_delete_system,
    can_revise_system,
    can_view_system,
)
from workspaces.services import create_organisation_workspace

User = get_user_model()
PASSWORD = "Scientific-Plan6-Password!42"


def make_user(email):
    return User.objects.create_user(email=email, password=PASSWORD)


def make_project(owner, workspace):
    return create_project(
        actor=owner,
        workspace=workspace,
        name="Scientific context project",
        description="System context tests",
        domain="mechanics",
    )


def draft_context(**overrides):
    data = {
        "documentation_status": RevisionDocumentationStatus.DRAFT,
        "description": "Rotor scientific context",
        "domain": "mechanics",
        "system_type": "rotating machine",
        "mechanism": "rotational oscillation under load",
        "environment": "laboratory",
        "measurement_context": "Encoder measurement",
        "scientific_notes": "Context only; no analysis result.",
        "revision_reason": "Initial definition",
        "a_ref_value_text": "1.2",
        "a_ref_unit": "rad",
        "a_ref_origin": "CALIBRATION",
        "a_ref_origin_detail": "CAL-2026-014",
        "a_ref_justification": "Reference amplitude from calibration.",
        "tau_value_text": "0.8",
        "tau_unit": "s",
        "tau_origin": "CALIBRATION",
        "tau_origin_detail": "CAL-2026-014",
        "tau_justification": "Measured mechanical relaxation timescale.",
        "w_mode": MemoryWindowMode.UNSPECIFIED,
        "w_value_text": "",
        "w_unit": "",
        "w_origin": "",
        "w_origin_detail": "",
        "w_justification": "",
        "p_c_mode": "FIXED",
        "p_c_value_text": "250",
        "p_c_unit": "W",
        "p_c_origin": "MANUFACTURER",
        "p_c_origin_detail": "MTR-04 datasheet",
        "p_c_justification": "Characteristic power from motor specification.",
    }
    data.update(overrides)
    return data


def primary_observable(**overrides):
    data = {
        "name": "Rotor angular position",
        "symbol": "theta_rotor",
        "description": "Angular position of the rotor.",
        "unit": "rad",
        "observable_kind": "angle",
        "nature": "MEASUREMENT",
        "source_description": "Encoder ENC-04",
        "is_primary": True,
    }
    data.update(overrides)
    return data


def make_system(owner, project, **context_overrides):
    return create_system(
        actor=owner,
        project=project,
        name="Rotor MTR-04",
        description="Stable System identity",
        revision_data=draft_context(**context_overrides),
        observables=[primary_observable()],
        references=[
            {
                "title": "Calibration report",
                "citation": "CAL-2026-014",
                "doi": "",
                "url": "",
                "notes": "Internal calibration protocol.",
                "supports_a_ref": True,
                "supports_tau": True,
                "supports_w": False,
                "supports_p_c": False,
            }
        ],
    )


@pytest.mark.django_db
def test_system_is_project_owned_uuid_with_creator_and_revision_snapshot():
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="System Lab")
    project = make_project(owner, workspace)
    system = make_system(owner, project)

    assert isinstance(system.pk, uuid.UUID)
    assert system.project == project
    assert system.created_by == owner
    assert system.current_revision.revision_number == 1
    assert system.current_revision.a_ref_value == pytest.approx(1.2)
    assert system.current_revision.tau_value == pytest.approx(0.8)
    assert system.current_revision.w_mode == MemoryWindowMode.UNSPECIFIED
    assert system.current_revision.w_value is None
    assert system.current_revision.p_c_value == pytest.approx(250)


@pytest.mark.django_db
def test_revision_is_immutable_and_new_revision_preserves_history():
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Revision Lab")
    project = make_project(owner, workspace)
    system = make_system(owner, project)
    revision1 = system.current_revision

    revision2 = create_system_revision(
        actor=owner,
        system=system,
        revision_data=draft_context(tau_value_text="1.1", revision_reason="New calibration"),
        observables=[primary_observable()],
        references=[],
    )
    revision1.refresh_from_db()
    system.refresh_from_db()

    assert revision1.revision_number == 1
    assert revision1.tau_value == pytest.approx(0.8)
    assert revision2.revision_number == 2
    assert revision2.tau_value == pytest.approx(1.1)
    assert system.current_revision == revision2
    revision1.tau_value_text = "99"
    with pytest.raises(ValidationError, match="immutable"):
        revision1.save()


@pytest.mark.django_db
def test_unspecified_w_is_distinct_from_explicit_w_equal_tau():
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Memory Lab")
    project = make_project(owner, workspace)
    system = make_system(owner, project)
    unspecified = system.current_revision

    explicit = create_system_revision(
        actor=owner,
        system=system,
        revision_data=draft_context(
            w_mode=MemoryWindowMode.EXPLICIT,
            w_value_text="0.8",
            w_unit="s",
            w_origin="CONVENTION",
            w_justification="Explicit sensitivity baseline.",
        ),
        observables=[primary_observable()],
        references=[],
    )

    assert unspecified.w_mode == MemoryWindowMode.UNSPECIFIED
    assert unspecified.w_value is None
    assert explicit.w_mode == MemoryWindowMode.EXPLICIT
    assert explicit.w_value == pytest.approx(explicit.tau_value)
    assert unspecified.configuration_fingerprint != explicit.configuration_fingerprint


@pytest.mark.django_db
def test_public_contract_allows_zero_characteristic_power_but_rejects_negative():
    parsed, _issues = validate_revision_context(
        draft_context(p_c_value_text="0"), [primary_observable()]
    )
    assert parsed["p_c_value"] == 0

    with pytest.raises(ValidationError, match="non-negative"):
        validate_revision_context(draft_context(p_c_value_text="-1"), [primary_observable()])


@pytest.mark.django_db
def test_known_unit_contracts_and_unknown_units_are_not_guessed():
    with pytest.raises(ValidationError, match="dimensionally compatible"):
        validate_revision_context(draft_context(a_ref_unit="kg"), [primary_observable(unit="m/s")])
    with pytest.raises(ValidationError, match="time-dimensional"):
        validate_revision_context(draft_context(tau_unit="kg"), [primary_observable()])
    with pytest.raises(ValidationError, match="power-dimensional"):
        validate_revision_context(draft_context(p_c_unit="kg"), [primary_observable()])

    parsed, issues = validate_revision_context(
        draft_context(tau_unit="custom-timescale-unit"), [primary_observable()]
    )
    assert parsed["tau_unit"] == "custom-timescale-unit"
    assert any(issue.code == "UNKNOWN_TAU_UNIT" for issue in issues)


@pytest.mark.django_db
def test_documented_revision_requires_scientific_context_but_draft_can_start_incomplete():
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Completeness Lab")
    project = make_project(owner, workspace)

    draft = create_system(
        actor=owner,
        project=project,
        name="Incomplete system",
        description="",
        revision_data=draft_context(
            a_ref_value_text="",
            a_ref_unit="",
            a_ref_origin="",
            a_ref_justification="",
            tau_value_text="",
            tau_unit="",
            tau_origin="",
            tau_justification="",
            p_c_value_text="",
            p_c_unit="",
            p_c_origin="",
            p_c_justification="",
        ),
        observables=[],
        references=[],
    )
    assert draft.current_revision.documentation_status == RevisionDocumentationStatus.DRAFT

    with pytest.raises(ValidationError):
        create_system_revision(
            actor=owner,
            system=draft,
            revision_data=draft_context(
                documentation_status=RevisionDocumentationStatus.DOCUMENTED,
                tau_justification="",
            ),
            observables=[primary_observable()],
            references=[],
        )


@pytest.mark.django_db
def test_configuration_fingerprint_is_deterministic_and_scientific_content_sensitive():
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Fingerprint Lab")
    project = make_project(owner, workspace)
    system = make_system(owner, project)
    revision = system.current_revision

    assert revision.configuration_fingerprint == configuration_fingerprint(revision)
    original = revision.configuration_fingerprint
    revision2 = create_system_revision(
        actor=owner,
        system=system,
        revision_data=draft_context(tau_value_text="1.2"),
        observables=[primary_observable()],
        references=[],
    )
    assert revision2.configuration_fingerprint != original


@pytest.mark.django_db
def test_current_revision_cannot_cross_link_systems():
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Cross Link Lab")
    project = make_project(owner, workspace)
    first = make_system(owner, project)
    second = create_system(
        actor=owner,
        project=project,
        name="Second system",
        description="",
        revision_data=draft_context(),
        observables=[primary_observable()],
        references=[],
    )
    first.current_revision = second.current_revision
    with pytest.raises(ValidationError, match="another system"):
        first.full_clean()


@pytest.mark.django_db
def test_system_permissions_make_analyst_scientific_author_and_viewer_read_only():
    owner = make_user("owner@example.com")
    editor = make_user("editor@example.com")
    analyst = make_user("analyst@example.com")
    viewer = make_user("viewer@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Permission Lab")
    for user, role in (
        (editor, WorkspaceRole.EDITOR),
        (analyst, WorkspaceRole.ANALYST),
        (viewer, WorkspaceRole.VIEWER),
    ):
        WorkspaceMembership.objects.create(user=user, workspace=workspace, role=role)
    project = make_project(owner, workspace)
    system = make_system(owner, project)

    assert can_create_system(owner, project)
    assert can_create_system(editor, project)
    assert can_create_system(analyst, project)
    assert not can_create_system(viewer, project)
    assert can_revise_system(analyst, system)
    assert can_view_system(viewer, system)
    assert can_delete_system(owner, system)
    assert not can_delete_system(editor, system)
    assert not can_delete_system(analyst, system)


@pytest.mark.django_db
def test_non_member_cannot_discover_system_detail_or_revision(client):
    owner = make_user("owner@example.com")
    outsider = make_user("outsider@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Private System Lab")
    project = make_project(owner, workspace)
    system = make_system(owner, project)
    client.force_login(outsider)
    args = [workspace.slug, project.pk, project.slug, system.pk, system.slug]

    response = client.get(reverse("systems:detail", args=args))
    revision_response = client.get(reverse("systems:revision-detail", args=[*args, 1]))
    revise_response = client.get(reverse("systems:revise", args=args))

    assert response.status_code == 404
    assert revision_response.status_code == 404
    assert revise_response.status_code == 404
    assert b"Rotor MTR-04" not in response.content


@pytest.mark.django_db
def test_viewer_cannot_mutate_system_directly(client):
    owner = make_user("owner@example.com")
    viewer = make_user("viewer@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Read Only System Lab")
    WorkspaceMembership.objects.create(user=viewer, workspace=workspace, role=WorkspaceRole.VIEWER)
    project = make_project(owner, workspace)
    system = make_system(owner, project)
    client.force_login(viewer)
    args = [workspace.slug, project.pk, project.slug, system.pk, system.slug]

    assert client.get(reverse("systems:detail", args=args)).status_code == 200
    assert client.get(reverse("systems:revise", args=args)).status_code == 403
    assert client.post(reverse("systems:archive", args=args)).status_code == 403


@pytest.mark.django_db
def test_project_delete_is_blocked_while_system_exists():
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Retention Lab")
    project = make_project(owner, workspace)
    make_system(owner, project)

    with pytest.raises(ValidationError, match="contains systems"):
        delete_project(actor=owner, project=project)
    assert System.objects.filter(project=project).exists()


@pytest.mark.django_db
def test_duplicate_system_copies_scientific_context_not_identity_or_history():
    owner = make_user("owner@example.com")
    analyst = make_user("analyst@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Duplicate Lab")
    WorkspaceMembership.objects.create(user=analyst, workspace=workspace, role=WorkspaceRole.ANALYST)
    project = make_project(owner, workspace)
    source = make_system(owner, project)
    create_system_revision(
        actor=owner,
        system=source,
        revision_data=draft_context(tau_value_text="1.1"),
        observables=[primary_observable()],
        references=[],
    )
    source.refresh_from_db()

    clone = duplicate_system(actor=analyst, system=source)

    assert clone.pk != source.pk
    assert clone.project == source.project
    assert clone.created_by == analyst
    assert clone.duplicated_from == source
    assert clone.current_revision.revision_number == 1
    assert clone.current_revision.tau_value == pytest.approx(source.current_revision.tau_value)
    assert clone.revisions.count() == 1


@pytest.mark.django_db
def test_archive_restore_preserves_revision_history():
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Lifecycle Lab")
    project = make_project(owner, workspace)
    system = make_system(owner, project)
    revision_id = system.current_revision_id

    archive_system(actor=owner, system=system)
    system.refresh_from_db()
    assert system.status == "ARCHIVED"
    restore_system(actor=owner, system=system)
    system.refresh_from_db()
    assert system.status == "ACTIVE"
    assert system.current_revision_id == revision_id


@pytest.mark.django_db
def test_database_prevents_two_primary_observables_in_one_revision():
    owner = make_user("owner@example.com")
    workspace = create_organisation_workspace(owner=owner, name="Observable Lab")
    project = make_project(owner, workspace)
    system = make_system(owner, project)
    revision = system.current_revision

    with pytest.raises(IntegrityError):
        ObservableDefinition.objects.create(
            revision=revision,
            position=2,
            name="Second primary",
            unit="rad",
            nature="MEASUREMENT",
            is_primary=True,
        )


@pytest.mark.django_db
def test_labbridge_reflects_required_public_context_arguments_without_running_analysis():
    contract = inspect_public_context_contract()
    assert contract.lab_version == SUPPORTED_AGENCITYLAB_VERSION
    assert contract.compatible
    assert {
        "A_ref",
        "tau",
        "w",
        "P_c",
        "unit",
        "domain",
        "mechanism",
        "system_type",
    }.issubset(contract.available_arguments)