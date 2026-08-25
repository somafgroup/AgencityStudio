"""Scientific-context validation without executing AgencityLab computations."""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from common.units import inspect_unit, unit_matches_reference, units_are_compatible
from labbridge.scientific_context import validate_physical_scalar

from .models import MemoryWindowMode, RevisionDocumentationStatus


@dataclass(frozen=True)
class ContextIssue:
    code: str
    level: str
    message: str


def _required_text(data: dict, key: str, label: str, issues: list[ContextIssue]) -> None:
    if not str(data.get(key, "")).strip():
        issues.append(ContextIssue(f"MISSING_{key.upper()}", "WARNING", _("%(label)s is missing.") % {"label": label}))


def _unit_warning(label: str, parameter: str, issues: list[ContextIssue]) -> None:
    if label and not inspect_unit(label).recognized:
        issues.append(
            ContextIssue(
                f"UNKNOWN_{parameter.upper()}_UNIT",
                "WARNING",
                _("Unit '%(unit)s' is preserved but cannot be automatically validated.") % {"unit": label},
            )
        )


def validate_revision_context(data: dict, observables: list[dict]) -> tuple[dict, list[ContextIssue]]:
    """Validate one proposed revision and return parsed scalar values plus warnings."""
    parsed = dict(data)
    issues: list[ContextIssue] = []

    parsed["a_ref_value"] = validate_physical_scalar("A_ref", data.get("a_ref_value_text"))
    parsed["tau_value"] = validate_physical_scalar("tau", data.get("tau_value_text"))
    parsed["p_c_value"] = validate_physical_scalar("P_c", data.get("p_c_value_text"))

    w_mode = data.get("w_mode") or MemoryWindowMode.UNSPECIFIED
    if w_mode == MemoryWindowMode.EXPLICIT:
        parsed["w_value"] = validate_physical_scalar("w", data.get("w_value_text"))
        if parsed["w_value"] is None:
            raise ValidationError({"w_value_text": _("Enter w when the memory window is explicit.")})
    elif w_mode == MemoryWindowMode.UNSPECIFIED:
        parsed["w_value"] = None
        parsed["w_value_text"] = ""
        parsed["w_unit"] = ""
        parsed["w_origin"] = ""
        parsed["w_origin_detail"] = ""
        parsed["w_justification"] = ""
    else:
        raise ValidationError({"w_mode": _("Unknown memory-window mode.")})

    primaries = [observable for observable in observables if observable.get("is_primary")]
    if len(primaries) > 1:
        raise ValidationError(_("Only one observable may be primary in a revision."))
    primary = primaries[0] if primaries else None

    if primary:
        compatibility = units_are_compatible(primary.get("unit"), data.get("a_ref_unit"))
        if compatibility is False:
            raise ValidationError(
                {"a_ref_unit": _("A_ref unit must be dimensionally compatible with the primary observable unit.")}
            )
        _unit_warning(str(primary.get("unit", "")).strip(), "observable", issues)
    _unit_warning(str(data.get("a_ref_unit", "")).strip(), "a_ref", issues)

    tau_unit = str(data.get("tau_unit", "")).strip()
    tau_dimension = unit_matches_reference(tau_unit, "second") if tau_unit else None
    if tau_dimension is False:
        raise ValidationError({"tau_unit": _("tau must use a time-dimensional unit.")})
    _unit_warning(tau_unit, "tau", issues)

    if w_mode == MemoryWindowMode.EXPLICIT:
        w_unit = str(data.get("w_unit", "")).strip()
        w_dimension = unit_matches_reference(w_unit, "second") if w_unit else None
        if w_dimension is False:
            raise ValidationError({"w_unit": _("w must use a time-dimensional unit.")})
        _unit_warning(w_unit, "w", issues)

    power_unit = str(data.get("p_c_unit", "")).strip()
    power_dimension = unit_matches_reference(power_unit, "watt") if power_unit else None
    if power_dimension is False:
        raise ValidationError({"p_c_unit": _("P_c must use a power-dimensional unit when the unit is recognized.")})
    _unit_warning(power_unit, "p_c", issues)

    if data.get("documentation_status") == RevisionDocumentationStatus.DOCUMENTED:
        if not primary:
            issues.append(ContextIssue("MISSING_PRIMARY_OBSERVABLE", "WARNING", _("A documented revision needs a primary observable.")))
        elif not str(primary.get("unit", "")).strip():
            issues.append(ContextIssue("MISSING_OBSERVABLE_UNIT", "WARNING", _("The primary observable needs a unit.")))

        required_values = (
            ("a_ref_value", "A_ref"),
            ("tau_value", "tau"),
            ("p_c_value", "P_c"),
        )
        for key, label in required_values:
            if parsed.get(key) is None:
                issues.append(ContextIssue(f"MISSING_{key.upper()}", "WARNING", _("%(label)s is missing.") % {"label": label}))

        for prefix, label in (("a_ref", "A_ref"), ("tau", "tau"), ("p_c", "P_c")):
            _required_text(data, f"{prefix}_unit", _("%(label)s unit") % {"label": label}, issues)
            _required_text(data, f"{prefix}_origin", _("%(label)s origin") % {"label": label}, issues)
            _required_text(data, f"{prefix}_justification", _("%(label)s justification") % {"label": label}, issues)

        if w_mode == MemoryWindowMode.EXPLICIT:
            if parsed.get("w_value") is None:
                issues.append(ContextIssue("MISSING_W_VALUE", "WARNING", _("Explicit w needs a value.")))
            _required_text(data, "w_unit", _("w unit"), issues)
            _required_text(data, "w_origin", _("w origin"), issues)
            _required_text(data, "w_justification", _("w justification"), issues)

    return parsed, issues


def documented_context_is_complete(issues: list[ContextIssue]) -> bool:
    """Return whether no documentation-completeness warning remains."""
    return not any(issue.level == "WARNING" and issue.code.startswith("MISSING_") for issue in issues)
