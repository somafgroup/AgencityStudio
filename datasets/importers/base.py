"""Small importer contracts for raw tabular sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from typing import BinaryIO


@dataclass(frozen=True)
class TabularSource:
    """One importer-neutral view of a tabular raw source."""

    headers: list[str]
    source_headers: list[str]
    rows: Iterator[list[object]]
    detected_options: dict
    metadata: dict


class ImporterError(ValueError):
    """Expected, user-facing importer failure without parser traceback leakage."""


class BaseImporter(ABC):
    importer_id = "base"
    schema_version = "1"

    @abstractmethod
    def open_table(self, handle: BinaryIO, *, filename: str, options: dict) -> TabularSource:
        """Return headers and a streaming row iterator for one source artifact."""
        raise NotImplementedError

    @abstractmethod
    def read_page(
        self,
        handle: BinaryIO,
        *,
        filename: str,
        options: dict,
        offset: int,
        limit: int,
    ) -> tuple[list[str], list[list[object]]]:
        """Read one server-side preview page without returning the whole source."""
        raise NotImplementedError
