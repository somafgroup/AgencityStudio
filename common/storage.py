"""Storage abstraction for future local and object storage backends."""

from pathlib import Path


class Storage:
    def save(self, name: str, data: bytes) -> str:
        raise NotImplementedError


class LocalStorage(Storage):
    def __init__(self, root: str = "storage") -> None:
        self.root = Path(root)

    def save(self, name: str, data: bytes) -> str:
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target)
