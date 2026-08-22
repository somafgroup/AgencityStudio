"""Contracts for the AgencityLab integration boundary.

This module intentionally contains no scientific equations.
"""

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version

from .service import SUPPORTED_AGENCITYLAB_VERSION, get_lab_version


@dataclass(frozen=True)
class LabCompatibility:
    """Runtime compatibility information exposed by Studio."""

    studio_version: str
    lab_version: str
    supported_lab_version: str
    compatible: bool


def compatibility() -> LabCompatibility:
    """Return the installed Studio/Lab compatibility contract."""
    try:
        studio_version = version("agencitystudio")
    except PackageNotFoundError:
        studio_version = "development"

    lab_version = get_lab_version()
    return LabCompatibility(
        studio_version=studio_version,
        lab_version=lab_version,
        supported_lab_version=SUPPORTED_AGENCITYLAB_VERSION,
        compatible=lab_version == SUPPORTED_AGENCITYLAB_VERSION,
    )
