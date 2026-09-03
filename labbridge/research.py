"""Public AgencityLab RESEARCH-field execution boundary.

Studio contains no autonomous-field equation, finite-difference operator,
topology formula, thermodynamic formula, or gravity formula. Every scientific
operation in this module delegates to documented public AgencityLab namespaces.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ResearchExecution:
    result: Any
    derived: dict[str, np.ndarray]
    warnings: tuple[dict[str, str], ...]


class ResearchLabError(RuntimeError):
    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category


def public_fields_api():
    """Return the documented public ``agencitylab.fields`` namespace."""

    from agencitylab import fields

    return fields


def public_thermodynamics_api():
    """Return the documented public ``agencitylab.thermodynamics`` namespace."""

    from agencitylab import thermodynamics

    return thermodynamics


def make_grid(*, axes):
    """Construct Lab's public uniform rectilinear grid from exact axes."""

    return public_fields_api().UniformRectilinearGrid(axes=tuple(axes))


def make_generated_grid(*, shape, spacings, origins):
    """Construct Lab's public deterministic grid without Studio coordinate formulas."""

    return public_fields_api().UniformRectilinearGrid(
        shape=tuple(shape), spacings=tuple(spacings), origins=tuple(origins)
    )


def make_potential(*, lambda_: float, mu: float):
    """Construct the public quartic research potential."""

    return public_fields_api().QuarticAgencityPotential(lambda_=lambda_, mu=mu)


def make_boundary(*, kind: str, value=0.0):
    """Construct one public Lab boundary object from an explicit Studio choice."""

    fields = public_fields_api()
    normalized = str(kind).upper()
    if normalized == "PERIODIC":
        return fields.PeriodicBoundary()
    if normalized == "DIRICHLET":
        return fields.DirichletBoundary(value=value)
    if normalized == "NEUMANN":
        return fields.NeumannBoundary(gradient=value)
    raise ValueError("boundary must be PERIODIC, DIRICHLET, or NEUMANN")


def bridge_beta_to_phi(*, beta, P_c, tau, time_axis: int):
    """Call the explicit public research bridge; no implicit promotion is permitted."""

    return public_fields_api().beta_to_phi(beta, P_c, tau, time_axis=int(time_axis))


def domain_wall_initial_field(
    *, x, lambda_: float, mu: float, center: float, orientation: int
):
    """Call Lab's public real-sector domain-wall reference generator."""

    return public_fields_api().domain_wall_profile(
        x,
        lambda_=lambda_,
        mu=mu,
        center=center,
        orientation=orientation,
    )


def vortex_initial_field(
    *, x, y, radial_profile, winding: int, lambda_: float, mu: float
):
    """Call Lab's public vortex constructor using a caller-supplied profile array."""

    return public_fields_api().vortex_field(
        x=x,
        y=y,
        radial_profile=radial_profile,
        winding=int(winding),
        lambda_=lambda_,
        mu=mu,
    )


def _topology_series(*, solution, contour_indices: tuple[int, ...]) -> np.ndarray:
    fields = public_fields_api()
    if len(contour_indices) < 3:
        raise ValueError("topology contour requires at least three ordered indices")
    flat_size = int(np.prod(solution.spatial_shape, dtype=int))
    if any(index < 0 or index >= flat_size for index in contour_indices):
        raise ValueError("a topology contour index is outside the autonomous field")
    values = []
    for frame in np.asarray(solution.phi):
        contour = np.asarray(frame).reshape(-1)[list(contour_indices)]
        values.append(fields.phase_winding(contour))
    return np.asarray(values, dtype=float)


def _thermodynamic_series(
    *, solution, grid, gamma: float, t_eff: float | None, entropy_a: float | None
) -> dict[str, np.ndarray]:
    thermo = public_thermodynamics_api()
    output: dict[str, np.ndarray] = {}
    if entropy_a is not None:
        output["field_agencial_entropy"] = np.asarray(
            [thermo.field_agencial_entropy(frame, entropy_a, grid) for frame in solution.phi],
            dtype=float,
        )
    if t_eff is not None:
        if solution.phi_dot is None:
            raise ValueError(
                "this public Lab solution does not expose phi_dot; dissipation and entropy-production postprocessing cannot be inferred"
            )
        output["total_dissipated_power"] = np.asarray(
            [thermo.total_dissipated_power(frame, gamma, grid) for frame in solution.phi_dot],
            dtype=float,
        )
        output["total_entropy_production"] = np.asarray(
            [
                thermo.total_entropy_production(frame, gamma, t_eff, grid)
                for frame in solution.phi_dot
            ],
            dtype=float,
        )
    return output


def execute_research_dynamics(
    *,
    model: str,
    phi0,
    phi_dot0,
    axes,
    lambda_: float,
    mu: float,
    gamma: float | None,
    dt_solver: float,
    n_steps: int,
    boundary_kind: str,
    boundary_value,
    metadata: dict | None = None,
    topology_contour_indices: tuple[int, ...] = (),
    thermo_t_eff: float | None = None,
    thermo_entropy_a: float | None = None,
) -> ResearchExecution:
    """Execute one exact public Lab autonomous-field solver and optional public postprocessors."""

    fields = public_fields_api()
    try:
        grid = make_grid(axes=axes)
        potential = make_potential(lambda_=lambda_, mu=mu)
        boundary = make_boundary(kind=boundary_kind, value=boundary_value)
        kwargs = {
            "grid": grid,
            "potential": potential,
            "dt": float(dt_solver),
            "n_steps": int(n_steps),
            "boundary": boundary,
            "metadata": dict(metadata or {}),
        }
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            if model == "KLEIN_GORDON":
                result = fields.simulate_klein_gordon(phi0, phi_dot0, **kwargs)
                resolved_gamma = 0.0
            elif model == "DISSIPATIVE_KLEIN_GORDON":
                result = fields.simulate_dissipative_klein_gordon(
                    phi0, phi_dot0, gamma=float(gamma), **kwargs
                )
                resolved_gamma = float(gamma)
            elif model == "TDGL":
                result = fields.simulate_tdgl(phi0, gamma=float(gamma), **kwargs)
                resolved_gamma = float(gamma)
            else:
                raise ValueError("unknown public autonomous-field model")

            derived: dict[str, np.ndarray] = {}
            if topology_contour_indices:
                derived["phase_winding"] = _topology_series(
                    solution=result,
                    contour_indices=tuple(int(item) for item in topology_contour_indices),
                )
            derived.update(
                _thermodynamic_series(
                    solution=result,
                    grid=grid,
                    gamma=resolved_gamma,
                    t_eff=thermo_t_eff,
                    entropy_a=thermo_entropy_a,
                )
            )
    except (TypeError, ValueError) as exc:
        raise ResearchLabError("LAB_VALIDATION_ERROR", str(exc)) from exc
    except RuntimeError as exc:
        raise ResearchLabError("LAB_EXECUTION_ERROR", str(exc)) from exc
    return ResearchExecution(
        result=result,
        derived=derived,
        warnings=tuple(
            {"category": item.category.__name__, "message": str(item.message)}
            for item in captured
        ),
    )
