"""AgencityLab integration contracts."""

from importlib.metadata import version, PackageNotFoundError


def get_lab_version() -> str:
    """Return the installed AgencityLab version when available."""
    try:
        return version("agencitylab")
    except PackageNotFoundError:
        return "not-installed"
