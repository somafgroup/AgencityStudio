"""Private Dataset artifact storage selection."""

from django.conf import settings

from common.storage import LocalStorage, Storage


def dataset_storage() -> Storage:
    """Return the configured private Dataset storage backend.

    Plan 4 ships the local backend. The service boundary intentionally allows an
    S3-compatible or institutional backend to be added without changing Dataset models.
    """
    return LocalStorage(settings.DATASET_STORAGE_ROOT)
