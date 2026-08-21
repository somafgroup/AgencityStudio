"""Template context shared by the AgencityStudio application shell."""

from importlib.metadata import PackageNotFoundError, version

from labbridge.service import get_lab_version


def system_info(request):
    """Expose non-sensitive version metadata to templates."""
    try:
        studio_version = version("agencitystudio")
    except PackageNotFoundError:
        studio_version = "development"

    return {
        "studio_version": studio_version,
        "agencitylab_version": get_lab_version(),
    }
