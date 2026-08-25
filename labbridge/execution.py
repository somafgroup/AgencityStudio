"""Canonical AgencityLab execution boundary for Studio.

This module only adapts validated representations to the public AgencityLab API.
It contains no Theory of Agencity equations and never preprocesses source data.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

from .service import public_api


@dataclass(frozen=True)
class CanonicalExecution:
    """Public Lab result plus warnings emitted during the public API call."""

    result: Any
    warnings: tuple[dict[str, str], ...]


class CanonicalLabError(RuntimeError):
    """Normalized integration failure preserving a lightweight public category."""

    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category


def execute_canonical_analysis(
    *,
    u,
    xi,
    A_ref: float,
    tau: float,
    w: float | None,
    P_c: float,
    unit: str = "",
    coordinate_unit: str = "",
    power_unit: str = "",
    observable_kind: str = "",
    domain: str = "",
    mechanism: str = "",
    system_type: str = "",
    environment: str = "",
    geometry: str = "",
    metadata: dict | None = None,
) -> CanonicalExecution:
    """Call ``agencitylab.compute_agencity`` with Studio-validated inputs unchanged."""
    api = public_api()
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            result = api.compute_agencity(
                u=u,
                xi=xi,
                A_ref=A_ref,
                tau=tau,
                w=w,
                P_c=P_c,
                unit=unit,
                coordinate_unit=coordinate_unit,
                power_unit=power_unit,
                observable_kind=observable_kind,
                domain=domain,
                mechanism=mechanism,
                system_type=system_type,
                environment=environment,
                geometry=geometry,
                metadata=metadata,
            )
    except (api.AgencityValidationError, api.PhysicalParameterError, api.UnitValidationError) as exc:
        raise CanonicalLabError("LAB_VALIDATION_ERROR", str(exc)) from exc
    except api.AgencityError as exc:
        raise CanonicalLabError("LAB_EXECUTION_ERROR", str(exc)) from exc
    return CanonicalExecution(
        result=result,
        warnings=tuple(
            {
                "category": item.category.__name__,
                "message": str(item.message),
            }
            for item in captured
        ),
    )
