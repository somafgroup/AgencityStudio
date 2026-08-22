"""CI settings: fast test behavior backed by the real PostgreSQL service."""

import os

from .test import *

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "agencitystudio"),
        "USER": os.getenv("POSTGRES_USER", "agencitystudio"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "agencitystudio"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}
