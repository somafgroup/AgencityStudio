"""Shared task primitives for AgencityStudio."""

from enum import StrEnum

from celery import shared_task


class TaskStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@shared_task(name="common.health_ping")
def health_ping() -> str:
    """Return a deterministic payload used to validate worker execution."""
    return "pong"
