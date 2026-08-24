"""Studio-side reflection of the AgencityLab 1.1.3 public context contract.

This module contains input-contract validation only. It never calls the
Agencity pipeline and contains no Theory of Agencity equations.
"""

from __future__ import annotations

import inspect
import math
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from .service import SUPPORTED_AGENCITYLAB_VERSION, public_api

PUBLIC_CONTEXT_ARGUMENTS = frozenset(
    {
        "A_ref",
        "tau",
        "w",
        "P_c",
        "unit",
        "coordinate_unit",
        "power_unit",
        "observable_kind",
        "domain",
        "mechanism",
        "system_type",
        "environment",
        "geometry",
        "metadata",
    }
)


@dataclass(frozen=True)
class PublicContextContract:
    """Observable compatibility facts from the public compute signature."""

    lab_version: str
    available_arguments: frozenset[str]
    missing_arguments: frozenset[str]

    @property
    def compatible(self) -> bool:
        return not self.missing_arguments


def inspect_public_context_contract() -> PublicContextContract:
    """Inspect ``agencitylab.compute_agencity`` without executing it."""
    api = public_api()
    parameters = frozenset(inspect.signature(api.compute_agencity).parameters)
    return PublicContextContract(
        lab_version=SUPPORTED_AGENCITYLAB_VERSION,
        available_arguments=parameters,
        missing_arguments=PUBLIC_CONTEXT_ARGUMENTS - parameters,
    )


def validate_physical_scalar(name: str, value: object, *, required: bool = False) -> float | None:
    """Validate the scalar contracts documented by AgencityLab 1.1.3.

    ``A_ref``, ``tau`` and explicit ``w`` are strictly positive. Scalar
    ``P_c`` is non-negative. All supplied values must be finite.
    """
    if value in (None, ""):
        if required:
            raise ValidationError(_("%(name)s is required.") % {"name": name})
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(_("%(name)s must be numeric.") % {"name": name}) from exc
    if not math.isfinite(number):
        raise ValidationError(_("%(name)s must be finite.") % {"name": name})
    if name == "P_c":
        if number < 0:
            raise ValidationError(_("P_c must be non-negative."))
    elif number <= 0:
        raise ValidationError(_("%(name)s must be strictly positive.") % {"name": name})
    return number
