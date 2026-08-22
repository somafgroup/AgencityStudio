"""Storage abstraction for future local and object storage backends."""

from abc import ABC, abstractmethod
from pathlib import Path


class Storage(ABC):
    """Minimal storage contract used by Studio services."""

    @abstractmethod
    def save(self, name: str, data: bytes) -> str:
        """Persist bytes and return the backend path or object identifier."""
        raise NotImplementedError


class LocalStorage(Storage):
    """Filesystem backend that confines writes to a configured root directory."""

    def __init__(self, root: str = "storage") -> None:
        self.root = Path(root).resolve()

    def save(self, name: str, data: bytes) -> str:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Storage paths must remain relative to the storage root.")

        target = (self.root / relative).resolve()
        if target == self.root or self.root not in target.parents:
            raise ValueError("Storage path escapes the configured storage root.")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target)
