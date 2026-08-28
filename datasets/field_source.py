"""Safe immutable NPZ source support for observable spatial field analyses.

The NPZ container is treated only as a transport for exact NumPy arrays.  Studio
never reshapes, interpolates, resamples, smooths, normalizes, or spatially
aggregates these arrays while materializing an Analysis source.
"""

from __future__ import annotations

import hashlib
import math
import zipfile
from pathlib import PurePosixPath

import numpy as np
from django.conf import settings

from .storage import dataset_storage

FIELD_SOURCE_FORMAT = "NPZ"
FIELD_SOURCE_IMPORTER = "studio.npz-field-v1"
FIELD_SOURCE_KIND = "observable_spatial_field_source"


class FieldSourceError(ValueError):
    """Raised when an immutable NPZ source violates the Studio field contract."""


def _limits() -> tuple[int, int, int]:
    return (
        int(getattr(settings, "FIELD_MAX_ARRAYS", 64)),
        int(getattr(settings, "FIELD_MAX_ELEMENTS", 20_000_000)),
        int(getattr(settings, "FIELD_MAX_UNCOMPRESSED_BYTES", 512 * 1024 * 1024)),
    )


def _array_header(member) -> tuple[tuple[int, ...], bool, np.dtype]:
    version = np.lib.format.read_magic(member)
    if version == (1, 0):
        shape, fortran_order, dtype = np.lib.format.read_array_header_1_0(member)
    elif version == (2, 0):
        shape, fortran_order, dtype = np.lib.format.read_array_header_2_0(member)
    else:
        raise FieldSourceError(
            f"Unsupported NPY member format version {version[0]}.{version[1]}."
        )
    return tuple(int(value) for value in shape), bool(fortran_order), np.dtype(dtype)


def _hash_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as member:
        for chunk in iter(lambda: member.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_npz_source(handle) -> dict:
    """Inspect an NPZ source without allocating its declared arrays.

    ZIP member sizes and NPY headers are validated before any later NumPy array
    allocation. Object dtypes are rejected so no field workflow can require
    ``allow_pickle=True``.
    """

    max_arrays, max_elements, max_uncompressed = _limits()
    handle.seek(0)
    if not zipfile.is_zipfile(handle):
        raise FieldSourceError("The uploaded field source is not a valid NPZ/ZIP container.")
    handle.seek(0)
    arrays: list[dict] = []
    seen_keys: set[str] = set()
    total_elements = 0
    total_uncompressed = 0
    with zipfile.ZipFile(handle, "r") as archive:
        infos = archive.infolist()
        if not infos:
            raise FieldSourceError("The NPZ field source contains no arrays.")
        if len(infos) > max_arrays:
            raise FieldSourceError(
                f"The NPZ field source contains {len(infos)} members; the configured limit is {max_arrays}."
            )
        for info in infos:
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
                raise FieldSourceError("NPZ members must use simple non-traversing filenames.")
            if path.suffix.lower() != ".npy":
                raise FieldSourceError("NPZ field sources may contain only .npy array members.")
            key = path.stem
            if not key or key in seen_keys:
                raise FieldSourceError("NPZ array keys must be unique and non-empty.")
            seen_keys.add(key)
            total_uncompressed += int(info.file_size)
            if total_uncompressed > max_uncompressed:
                raise FieldSourceError(
                    "The NPZ field source exceeds the configured uncompressed-byte limit."
                )
            with archive.open(info, "r") as member:
                shape, fortran_order, dtype = _array_header(member)
            if dtype.hasobject:
                raise FieldSourceError(
                    f"Array {key!r} uses an object dtype; object/pickle arrays are not accepted."
                )
            elements = int(math.prod(shape)) if shape else 1
            if elements <= 0:
                raise FieldSourceError(f"Array {key!r} has an empty dimension.")
            if elements > max_elements:
                raise FieldSourceError(
                    f"Array {key!r} declares {elements} elements; the configured limit is {max_elements}."
                )
            total_elements += elements
            if total_elements > max_elements:
                raise FieldSourceError(
                    "The NPZ field source exceeds the configured total element limit."
                )
            expected_payload = elements * int(dtype.itemsize)
            if expected_payload > int(info.file_size):
                raise FieldSourceError(
                    f"Array {key!r} declares more payload bytes than its NPZ member contains."
                )
            arrays.append(
                {
                    "key": key,
                    "member": info.filename,
                    "shape": list(shape),
                    "ndim": len(shape),
                    "dtype": dtype.str,
                    "dtype_kind": dtype.kind,
                    "fortran_order": fortran_order,
                    "elements": elements,
                    "npy_size_bytes": int(info.file_size),
                    "npy_sha256": _hash_member(archive, info),
                }
            )
    return {
        "kind": FIELD_SOURCE_KIND,
        "container": "NPZ",
        "arrays": arrays,
        "array_count": len(arrays),
        "total_elements": total_elements,
        "total_uncompressed_bytes": total_uncompressed,
        "quality_counts": {"INFO": 0, "WARNING": 0, "ERROR": 0},
        "scientific_note": (
            "Array inventory only. Time/spatial axes and physical parameter meaning are configured explicitly in Analysis."
        ),
    }


def field_inventory(version) -> list[dict]:
    summary = dict(version.inspection_summary or {})
    if summary.get("kind") != FIELD_SOURCE_KIND:
        raise FieldSourceError("The selected Dataset Version is not an inspected NPZ field source.")
    return list(summary.get("arrays") or [])


def array_descriptor(version, key: str) -> dict:
    for descriptor in field_inventory(version):
        if descriptor.get("key") == key:
            return dict(descriptor)
    raise FieldSourceError(f"Array {key!r} is not present in the pinned field source.")


def _verify_source_sha256(handle, expected: str) -> None:
    digest = hashlib.sha256()
    handle.seek(0)
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
    if digest.hexdigest() != expected:
        raise FieldSourceError("The immutable field source failed SHA-256 verification.")
    handle.seek(0)


def load_npz_arrays(version, keys: list[str] | tuple[str, ...]) -> dict[str, np.ndarray]:
    """Load selected exact arrays from a pinned NPZ DatasetVersion.

    No axis movement, reshape, conversion, filling, or scientific preprocessing
    is performed. The source bytes are verified before NumPy materialization.
    """

    requested = list(dict.fromkeys(str(key) for key in keys))
    descriptors = {key: array_descriptor(version, key) for key in requested}
    storage = dataset_storage()
    if not storage.exists(version.source_path):
        raise FieldSourceError("The pinned field source is missing from private storage.")
    with storage.open(version.source_path, "rb") as handle:
        _verify_source_sha256(handle, version.source_sha256)
        try:
            with np.load(handle, allow_pickle=False) as archive:
                arrays = {key: np.asarray(archive[key]) for key in requested}
        except (KeyError, OSError, ValueError, zipfile.BadZipFile) as exc:
            raise FieldSourceError("The pinned NPZ field source could not be materialized safely.") from exc
    for key, array in arrays.items():
        descriptor = descriptors[key]
        if list(array.shape) != descriptor["shape"] or array.dtype.str != descriptor["dtype"]:
            raise FieldSourceError(
                f"Array {key!r} no longer matches its immutable inspection descriptor."
            )
        if array.dtype.hasobject:
            raise FieldSourceError("Object/pickle arrays are not accepted.")
    return arrays


def is_field_source(version) -> bool:
    return (
        str(version.source_format) == FIELD_SOURCE_FORMAT
        and (version.inspection_summary or {}).get("kind") == FIELD_SOURCE_KIND
    )
