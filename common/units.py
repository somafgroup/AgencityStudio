"""Shared Pint-backed unit parsing and dimensional compatibility helpers.

Units remain user-entered scientific metadata. These helpers validate known
units without converting or replacing the original representation.
"""

from __future__ import annotations

from dataclasses import dataclass

from pint import UndefinedUnitError, UnitRegistry

unit_registry = UnitRegistry(autoconvert_offset_to_baseunit=True)


@dataclass(frozen=True)
class UnitInspection:
    """Result of inspecting one user-provided unit label."""

    label: str
    recognized: bool
    normalized: str
    dimensionality: str


def inspect_unit(label: str | None) -> UnitInspection:
    """Inspect a unit label without changing the user's stored representation."""
    clean = str(label or "").strip()
    if not clean:
        return UnitInspection(label="", recognized=False, normalized="", dimensionality="")
    try:
        unit = unit_registry.Unit(clean)
    except (UndefinedUnitError, ValueError, TypeError):
        return UnitInspection(label=clean, recognized=False, normalized="", dimensionality="")
    return UnitInspection(
        label=clean,
        recognized=True,
        normalized=f"{unit:~}",
        dimensionality=str(unit.dimensionality),
    )


def units_are_compatible(left: str | None, right: str | None) -> bool | None:
    """Return compatibility for known units, or ``None`` when either is unknown."""
    left_info = inspect_unit(left)
    right_info = inspect_unit(right)
    if not left_info.recognized or not right_info.recognized:
        return None
    return unit_registry.Unit(left_info.label).dimensionality == unit_registry.Unit(
        right_info.label
    ).dimensionality


def unit_matches_reference(label: str | None, reference_unit: str) -> bool | None:
    """Return whether a known unit has the dimensionality of ``reference_unit``."""
    info = inspect_unit(label)
    if not info.recognized:
        return None
    return unit_registry.Unit(info.label).dimensionality == unit_registry.Unit(
        reference_unit
    ).dimensionality
