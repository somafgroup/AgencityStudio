"""Contracts for the AgencityLab integration boundary.

This module intentionally contains no scientific equations.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LabCompatibility:
    studio_version: str
    lab_version: str


def compatibility() -> LabCompatibility:
    return LabCompatibility(studio_version="0.x", lab_version="not-configured")
