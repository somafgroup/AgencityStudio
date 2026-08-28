"""Public AgencityLab observable-field execution boundary.

This adapter contains no Agencity equations. It forwards exact validated Studio
arrays and parameter representations to ``agencitylab.fields.compute_agencity_field``.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ObservableFieldExecution:
    result: Any
    warnings: tuple[dict[str, str], ...]


class ObservableFieldLabError(RuntimeError):
    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category


def public_fields_api():
    """Return the documented public ``agencitylab.fields`` module."""

    import agencitylab.fields as fields

    return fields


def execute_observable_field_analysis(
    *, u, t, spatial_axes, A_ref, tau, w, P_c, time_axis: int, metadata: dict | None = None
) -> ObservableFieldExecution:
    """Call the public experimental field API without Studio-side preprocessing."""

    fields = public_fields_api()
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            result = fields.compute_agencity_field(
                u=u,
                t=t,
                spatial_axes=spatial_axes,
                A_ref=A_ref,
                tau=tau,
                w=w,
                P_c=P_c,
                time_axis=int(time_axis),
                metadata=dict(metadata or {}),
            )
    except (TypeError, ValueError) as exc:
        raise ObservableFieldLabError("LAB_VALIDATION_ERROR", str(exc)) from exc
    except RuntimeError as exc:
        raise ObservableFieldLabError("LAB_EXECUTION_ERROR", str(exc)) from exc
    return ObservableFieldExecution(
        result=result,
        warnings=tuple(
            {"category": item.category.__name__, "message": str(item.message)}
            for item in captured
        ),
    )
