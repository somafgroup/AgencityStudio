"""Public AgencityLab multivariate execution boundary for Studio.

The AgencityLab 1.1.3 public contract lives at
``agencitylab.api.compute_multivariate_agencity``. This adapter forwards validated
Studio inputs unchanged and captures warnings. It contains no multivariate
Agencity equations, aggregation, preprocessing, alignment, normalization, or
parameter estimation.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

from .service import public_extended_api

MULTIVARIATE_PUBLIC_FUNCTION = "agencitylab.api.compute_multivariate_agencity"
MULTIVARIATE_SCIENTIFIC_STATUS = "Volume 2 multivariate extension"


@dataclass(frozen=True)
class MultivariateExecution:
    """Public Lab result plus warnings emitted during the public API call."""

    result: Any
    warnings: tuple[dict[str, str], ...]


class MultivariateLabError(RuntimeError):
    """Normalized public integration failure with a safe Studio category."""

    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category


def execute_multivariate_analysis(
    *,
    u,
    xi,
    A_ref,
    tau,
    P_c,
    w=None,
    sample_axis: int = 0,
) -> MultivariateExecution:
    """Call the public AgencityLab multivariate API with inputs unchanged."""
    api = public_extended_api()
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            result = api.compute_multivariate_agencity(
                u,
                xi,
                A_ref=A_ref,
                tau=tau,
                P_c=P_c,
                w=w,
                sample_axis=sample_axis,
            )
    except (api.AgencityValidationError, api.PhysicalParameterError, api.UnitValidationError, ValueError) as exc:
        raise MultivariateLabError("LAB_VALIDATION_ERROR", str(exc)) from exc
    except api.AgencityError as exc:
        raise MultivariateLabError("LAB_EXECUTION_ERROR", str(exc)) from exc

    return MultivariateExecution(
        result=result,
        warnings=tuple(
            {
                "category": item.category.__name__,
                "message": str(item.message),
            }
            for item in captured
        ),
    )
