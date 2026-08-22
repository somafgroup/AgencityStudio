"""Private storage primitives shared by Studio services."""

from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from typing import BinaryIO


class Storage(ABC):
    """Minimal private-artifact storage contract used by Studio services."""

    @abstractmethod
    def save(self, name: str, data: bytes) -> str:
        """Persist immutable bytes and return the backend object identifier."""
        raise NotImplementedError

    @abstractmethod
    def save_chunks(self, name: str, chunks: Iterable[bytes]) -> tuple[str, int, str]:
        """Persist immutable chunks and return path, byte size and exact-source SHA-256."""
        raise NotImplementedError

    @abstractmethod
    def open(self, name: str, mode: str = "rb") -> BinaryIO:
        """Open one private artifact after validating its backend-relative identifier."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, name: str) -> None:
        """Delete one private artifact if it exists."""
        raise NotImplementedError

    @abstractmethod
    def exists(self, name: str) -> bool:
        """Return whether an artifact exists."""
        raise NotImplementedError


class LocalStorage(Storage):
    """Filesystem backend that confines immutable artifacts to a configured root."""

    def __init__(self, root: str | Path = "storage") -> None:
        self.root = Path(root).resolve()

    def _relative(self, name: str) -> Path:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Storage paths must remain relative to the storage root.")
        return relative

    def _target(self, name: str) -> Path:
        target = (self.root / self._relative(name)).resolve()
        if target == self.root or self.root not in target.parents:
            raise ValueError("Storage path escapes the configured storage root.")
        return target

    def save(self, name: str, data: bytes) -> str:
        path, _, _ = self.save_chunks(name, (data,))
        return path

    def save_chunks(self, name: str, chunks: Iterable[bytes]) -> tuple[str, int, str]:
        target = self._target(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        digest = hashlib.sha256()
        size = 0
        try:
            with temporary.open("xb") as handle:
                for chunk in chunks:
                    if not chunk:
                        continue
                    handle.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            if target.exists():
                raise FileExistsError(f"Immutable artifact already exists: {name}")
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return name, size, digest.hexdigest()

    def open(self, name: str, mode: str = "rb") -> BinaryIO:
        if mode not in {"rb", "r"}:
            raise ValueError("Dataset artifact storage is read-only after creation.")
        return self._target(name).open(mode)

    def delete(self, name: str) -> None:
        self._target(name).unlink(missing_ok=True)

    def exists(self, name: str) -> bool:
        return self._target(name).is_file()
