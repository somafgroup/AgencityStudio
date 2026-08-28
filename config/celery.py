"""Celery application for asynchronous AgencityStudio work."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("agencitystudio")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.imports = (
    "analyses.diagnostic_tasks",
    "datasets.field_tasks",
)
app.autodiscover_tasks()
