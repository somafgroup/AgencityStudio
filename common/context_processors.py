"""Template context shared by the AgencityStudio application shell."""

from importlib.metadata import PackageNotFoundError, version

from labbridge.service import (
    SUPPORTED_AGENCITYLAB_VERSION,
    get_lab_version,
    lab_is_compatible,
)


def system_info(request):
    """Expose non-sensitive version and compatibility metadata to templates."""
    try:
        studio_version = version("agencitystudio")
    except PackageNotFoundError:
        studio_version = "development"

    return {
        "studio_version": studio_version,
        "agencitylab_version": get_lab_version(),
        "agencitylab_supported_version": SUPPORTED_AGENCITYLAB_VERSION,
        "agencitylab_compatible": lab_is_compatible(),
    }
