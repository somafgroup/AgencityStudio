"""AgencityLab integration services.

Only the public AgencityLab package surface may be imported here. Studio must
never duplicate or reach into the canonical implementation internals.
"""

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from types import ModuleType

SUPPORTED_AGENCITYLAB_VERSION = "1.1.3"


def get_lab_version() -> str:
    """Return the installed AgencityLab distribution version."""
    try:
        return version("agencitylab")
    except PackageNotFoundError:
        return "not-installed"


def lab_is_compatible() -> bool:
    """Return whether the installed Lab version matches Studio's runtime contract."""
    return get_lab_version() == SUPPORTED_AGENCITYLAB_VERSION


def public_api() -> ModuleType:
    """Load the documented AgencityLab package root and nothing below it."""
    return import_module("agencitylab")
