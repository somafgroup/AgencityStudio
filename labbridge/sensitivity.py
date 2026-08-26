"""Public AgencityLab 1.1.3 multiscale and window-sensitivity integration.

Studio supplies immutable source vectors and explicit physical/contextual inputs.
Every scientific scale/window computation remains inside public AgencityLab APIs.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
from agencitylab import AgencityError
from agencitylab.api import compute_agencity_spectrum, optimize_agencity_window

TAU_MULTISCALE_API = "agencitylab.api.compute_agencity_spectrum"
WINDOW_SENSITIVITY_API = "agencitylab.api.optimize_agencity_window"


class SensitivityLabError(RuntimeError):
    """Safe integration error raised at the Studio/Lab sensitivity boundary."""

    def __init__(self, message: str, *, category: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class SensitivityExecution:
    """Detached public Lab output plus captured public warnings and API identity."""

    result: dict[str, Any]
    warnings: tuple[dict[str, str], ...]
    api_identifier: str
    scientific_status: str


def _warning_payload(captured) -> tuple[dict[str, str], ...]:
    return tuple(
        {"category": item.category.__name__, "message": str(item.message)}
        for item in captured
    )


def execute_tau_multiscale(
    *,
    u: np.ndarray,
    xi: np.ndarray,
    taus: list[float],
    A_ref: float,
    P_c: float,
    requested_w_mode: str,
    requested_w: float | None,
) -> SensitivityExecution:
    """Call the public time-resolved ``b(t, tau)`` spectrum unchanged.

    ``UNSPECIFIED`` is deliberately transmitted as ``windows=None``. Studio never
    materializes the Lab fallback ``w=tau`` itself. An explicit base window is
    transmitted as one scalar and therefore remains fixed across all tau scales.
    """
    windows = None if requested_w_mode == "UNSPECIFIED" else requested_w
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            result = compute_agencity_spectrum(
                u,
                xi,
                taus,
                A_ref=A_ref,
                P_c=P_c,
                windows=windows,
                return_full=False,
            )
    except (TypeError, ValueError) as exc:
        raise SensitivityLabError(
            str(exc), category="LAB_SENSITIVITY_VALIDATION_ERROR"
        ) from exc
    except AgencityError as exc:
        raise SensitivityLabError(
            str(exc), category="LAB_SENSITIVITY_EXECUTION_ERROR"
        ) from exc
    except Exception as exc:
        raise SensitivityLabError(
            "AgencityLab multiscale execution failed.",
            category="LAB_SENSITIVITY_EXECUTION_ERROR",
        ) from exc
    return SensitivityExecution(
        result=result,
        warnings=_warning_payload(captured),
        api_identifier=TAU_MULTISCALE_API,
        scientific_status="SENSITIVITY_STUDY",
    )


def execute_window_sensitivity(
    *,
    u: np.ndarray,
    xi: np.ndarray,
    tau: float,
    A_ref: float,
    P_c: float,
    candidates: list[float],
) -> SensitivityExecution:
    """Call the public Chapter-13 Phi2 window-selection study unchanged.

    The returned ``w_opt`` is a Lab-reported numerical optimum under Phi2. Studio
    does not promote it to a physical/contextual memory constant.
    """
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            result = optimize_agencity_window(
                u,
                xi,
                tau=tau,
                A_ref=A_ref,
                P_c=P_c,
                candidates=candidates,
                n_candidates=len(candidates),
            )
    except (TypeError, ValueError) as exc:
        raise SensitivityLabError(
            str(exc), category="LAB_SENSITIVITY_VALIDATION_ERROR"
        ) from exc
    except AgencityError as exc:
        raise SensitivityLabError(
            str(exc), category="LAB_SENSITIVITY_EXECUTION_ERROR"
        ) from exc
    except Exception as exc:
        raise SensitivityLabError(
            "AgencityLab window-sensitivity execution failed.",
            category="LAB_SENSITIVITY_EXECUTION_ERROR",
        ) from exc
    return SensitivityExecution(
        result=result,
        warnings=_warning_payload(captured),
        api_identifier=WINDOW_SENSITIVITY_API,
        scientific_status="DIAGNOSTIC_EXPERIMENTAL",
    )
