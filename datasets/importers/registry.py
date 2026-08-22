"""Supported importer selection by validated source format."""

from .base import BaseImporter, ImporterError
from .delimited import DelimitedImporter
from .xlsx import XlsxImporter


def get_importer(source_format: str) -> BaseImporter:
    if source_format in {"CSV", "TSV", "TXT"}:
        return DelimitedImporter()
    if source_format == "XLSX":
        return XlsxImporter()
    raise ImporterError("This dataset source format is not supported.")
