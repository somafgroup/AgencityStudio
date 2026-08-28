"""Shape-only Studio validation for observable spatial field configuration.

This module validates representation contracts before execution.  It contains no
Agencity equations and never repairs source arrays.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from datasets.field_source import FieldSourceError, array_descriptor

from .field_contract import (
    PARAMETER_MODE_SCALAR,
    PARAMETER_MODE_SPATIAL,
    POWER_MODE_SPACETIME,
    SPATIAL_AXES_EXPLICIT,
    SPATIAL_AXES_SAMPLE_INDEX,
    WINDOW_MODE_UNSPECIFIED,
)

_REAL_KINDS = {"b", "i", "u", "f"}


@dataclass(frozen=True)
class FieldGeometry:
    field_shape: tuple[int, ...]
    time_axis: int
    time_length: int
    spatial_shape: tuple[int, ...]
    spatial_axis_descriptors: tuple[dict | None, ...]


def _real_numeric(descriptor: dict, label: str) -> None:
    if descriptor.get("dtype_kind") not in _REAL_KINDS:
        raise ValidationError(_("%(label)s must be a real numeric array.") % {"label": label})


def _normalize_time_axis(value: int, ndim: int) -> int:
    try:
        axis = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(_("time_axis must be an integer.")) from exc
    if axis < 0:
        axis += ndim
    if axis < 0 or axis >= ndim:
        raise ValidationError(_("time_axis is outside the observable array dimensions."))
    return axis


def validate_geometry(
    *, version, u_key: str, t_key: str, time_axis: int, spatial_axes_mode: str, spatial_axis_keys: list[str]
) -> FieldGeometry:
    try:
        u_descriptor = array_descriptor(version, u_key)
        t_descriptor = array_descriptor(version, t_key)
    except FieldSourceError as exc:
        raise ValidationError(str(exc)) from exc
    _real_numeric(u_descriptor, "u")
    _real_numeric(t_descriptor, "t")
    field_shape = tuple(int(value) for value in u_descriptor["shape"])
    if len(field_shape) < 2:
        raise ValidationError(_("u must have at least two dimensions for a spatial field."))
    axis = _normalize_time_axis(time_axis, len(field_shape))
    time_length = field_shape[axis]
    if time_length < 3:
        raise ValidationError(_("The temporal axis must contain at least three samples."))
    if tuple(t_descriptor["shape"]) != (time_length,):
        raise ValidationError(_("t must be one-dimensional and match u along time_axis exactly."))
    spatial_shape = field_shape[:axis] + field_shape[axis + 1 :]
    spatial_descriptors: list[dict | None] = []
    if spatial_axes_mode == SPATIAL_AXES_SAMPLE_INDEX:
        if spatial_axis_keys:
            raise ValidationError(_("Sample-index spatial axes must not include coordinate arrays."))
        spatial_descriptors = [None] * len(spatial_shape)
    elif spatial_axes_mode == SPATIAL_AXES_EXPLICIT:
        if len(spatial_axis_keys) != len(spatial_shape):
            raise ValidationError(
                _("Provide exactly one explicit coordinate array for each spatial dimension.")
            )
        for dimension, (key, length) in enumerate(
            zip(spatial_axis_keys, spatial_shape, strict=True), start=1
        ):
            try:
                descriptor = array_descriptor(version, key)
            except FieldSourceError as exc:
                raise ValidationError(str(exc)) from exc
            _real_numeric(descriptor, f"spatial axis {dimension}")
            if tuple(descriptor["shape"]) != (length,):
                raise ValidationError(
                    _("Spatial coordinate array %(key)s has the wrong length for dimension %(dimension)s.")
                    % {"key": key, "dimension": dimension}
                )
            spatial_descriptors.append(descriptor)
    else:
        raise ValidationError(_("Unknown spatial-axis mode."))
    return FieldGeometry(
        field_shape=field_shape,
        time_axis=axis,
        time_length=time_length,
        spatial_shape=spatial_shape,
        spatial_axis_descriptors=tuple(spatial_descriptors),
    )


def _map_descriptor(version, key: str, expected_shape: tuple[int, ...], label: str) -> dict:
    if not key:
        raise ValidationError(_("%(label)s map array is required.") % {"label": label})
    try:
        descriptor = array_descriptor(version, key)
    except FieldSourceError as exc:
        raise ValidationError(str(exc)) from exc
    _real_numeric(descriptor, label)
    if tuple(descriptor["shape"]) != tuple(expected_shape):
        raise ValidationError(
            _("%(label)s map must have exact shape %(shape)s.")
            % {"label": label, "shape": expected_shape}
        )
    return descriptor


def validate_parameter_modes(*, version, geometry: FieldGeometry, config: dict) -> dict[str, dict | None]:
    """Validate only public Lab parameter representation shapes."""

    descriptors: dict[str, dict | None] = {}
    for name in ("A_ref", "tau"):
        mode = config[f"{name}_mode"]
        if mode == PARAMETER_MODE_SCALAR:
            descriptors[name] = None
        elif mode == PARAMETER_MODE_SPATIAL:
            descriptors[name] = _map_descriptor(
                version,
                config.get(f"{name}_map_key", ""),
                geometry.spatial_shape,
                name,
            )
        else:
            raise ValidationError(_("Unknown %(name)s parameter mode.") % {"name": name})

    w_mode = config["w_mode"]
    if w_mode in {WINDOW_MODE_UNSPECIFIED, PARAMETER_MODE_SCALAR}:
        descriptors["w"] = None
    elif w_mode == PARAMETER_MODE_SPATIAL:
        descriptors["w"] = _map_descriptor(
            version, config.get("w_map_key", ""), geometry.spatial_shape, "w"
        )
    else:
        raise ValidationError(_("Unknown w parameter mode."))

    p_mode = config["P_c_mode"]
    if p_mode == PARAMETER_MODE_SCALAR:
        descriptors["P_c"] = None
    elif p_mode == PARAMETER_MODE_SPATIAL:
        descriptors["P_c"] = _map_descriptor(
            version, config.get("P_c_map_key", ""), geometry.spatial_shape, "P_c"
        )
    elif p_mode == POWER_MODE_SPACETIME:
        descriptors["P_c"] = _map_descriptor(
            version, config.get("P_c_map_key", ""), geometry.field_shape, "P_c"
        )
    else:
        raise ValidationError(_("Unknown P_c parameter mode."))
    return descriptors
