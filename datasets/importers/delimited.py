"""Streaming CSV/TSV/structured-text importer."""

from __future__ import annotations

import codecs
import csv
import io
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

from .base import BaseImporter, ImporterError, TabularSource

_DELIMITERS = [",", "\t", ";", "|"]


def _detect_encoding(sample: bytes) -> tuple[str, bool]:
    if sample.startswith(codecs.BOM_UTF8):
        return "utf-8-sig", True
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return "latin-1", True
    return "utf-8", True


def _detect_dialect(text: str, filename: str) -> tuple[str, bool]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".tsv":
        default_delimiter = "\t"
    else:
        default_delimiter = ","
    try:
        dialect = csv.Sniffer().sniff(text, delimiters="".join(_DELIMITERS))
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = default_delimiter
    try:
        has_header = csv.Sniffer().has_header(text)
    except csv.Error:
        has_header = True
    return delimiter, has_header


def _normalise_options(handle: BinaryIO, filename: str, options: dict) -> tuple[dict, dict]:
    handle.seek(0)
    sample_bytes = handle.read(65536)
    if not sample_bytes:
        raise ImporterError("The source file is empty.")
    detected_encoding, _ = _detect_encoding(sample_bytes)
    encoding = str(options.get("encoding") or detected_encoding).strip() or "utf-8"
    try:
        sample_text = sample_bytes.decode(encoding)
    except (LookupError, UnicodeDecodeError) as exc:
        raise ImporterError(f"The source could not be decoded using {encoding}.") from exc
    detected_delimiter, detected_header = _detect_dialect(sample_text, filename)
    delimiter = options.get("delimiter")
    if delimiter in {"\\t", "TAB", "tab"}:
        delimiter = "\t"
    delimiter = delimiter or detected_delimiter
    if not isinstance(delimiter, str) or len(delimiter) != 1:
        raise ImporterError("Delimiter must be exactly one character.")
    has_header = options.get("has_header")
    if has_header is None:
        has_header = detected_header
    else:
        has_header = bool(has_header)
    decimal_separator = options.get("decimal_separator") or "."
    if decimal_separator not in {".", ","}:
        raise ImporterError("Decimal separator must be '.' or ','.")
    used = {
        "encoding": encoding,
        "delimiter": delimiter,
        "has_header": has_header,
        "decimal_separator": decimal_separator,
    }
    detected = {
        "encoding": detected_encoding,
        "delimiter": detected_delimiter,
        "has_header": detected_header,
    }
    handle.seek(0)
    return used, detected


def _row_stream(handle: BinaryIO, *, encoding: str, delimiter: str) -> Iterator[list[str]]:
    wrapper = io.TextIOWrapper(handle, encoding=encoding, newline="")
    try:
        reader = csv.reader(wrapper, delimiter=delimiter)
        yield from reader
    except (csv.Error, UnicodeError) as exc:
        raise ImporterError("The delimited source could not be parsed with these import settings.") from exc
    finally:
        try:
            wrapper.detach()
        except (ValueError, AttributeError):
            pass


class DelimitedImporter(BaseImporter):
    importer_id = "studio.delimited"
    schema_version = "1"

    def open_table(self, handle: BinaryIO, *, filename: str, options: dict) -> TabularSource:
        used, detected = _normalise_options(handle, filename, options)
        rows = _row_stream(handle, encoding=used["encoding"], delimiter=used["delimiter"])
        try:
            first = next(rows)
        except StopIteration as exc:
            raise ImporterError("The source contains no rows.") from exc
        if used["has_header"]:
            source_headers = [str(value) for value in first]
            headers = [value if value.strip() else f"Column {index}" for index, value in enumerate(source_headers, 1)]
            data_rows = rows
        else:
            source_headers = ["" for _ in first]
            headers = [f"Column {index}" for index in range(1, len(first) + 1)]

            def include_first():
                yield first
                yield from rows

            data_rows = include_first()
        if not headers:
            raise ImporterError("The source contains no columns.")
        return TabularSource(
            headers=headers,
            source_headers=source_headers,
            rows=data_rows,
            detected_options=detected,
            metadata={"used_options": used, "source_has_header": used["has_header"]},
        )

    def read_page(
        self,
        handle: BinaryIO,
        *,
        filename: str,
        options: dict,
        offset: int,
        limit: int,
    ) -> tuple[list[str], list[list[object]]]:
        table = self.open_table(handle, filename=filename, options=options)
        page: list[list[object]] = []
        max_width = len(table.headers)
        for row_index, row in enumerate(table.rows):
            if row_index < offset:
                continue
            if len(page) >= limit:
                break
            values = list(row)
            page.append(values)
            max_width = max(max_width, len(values))
        headers = list(table.headers)
        headers.extend(f"Column {index}" for index in range(len(headers) + 1, max_width + 1))
        return headers, page
