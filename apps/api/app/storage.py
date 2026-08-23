"""Storage abstraction for immutable dataset artifacts (Phase 2 §34–§35, §42–§43).

``StorageProvider`` is a minimal protocol (put/get/delete/exists) so a future
S3/object-storage implementation can replace ``LocalStorageProvider`` without
changing callers. Storage keys are ALWAYS generated identifiers (never derived
from user-supplied filenames), which makes path traversal impossible.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from app.core.errors import InvalidDatasetSchemaError


class StorageProvider(Protocol):
    """Protocol for blob storage of immutable dataset artifacts."""

    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...


def sanitize_filename(filename: str | None) -> str:
    """Return a safe basename for display/recording (spec §42–§43).

    The returned value is informational only; storage keys are generated IDs
    and never derive from this. Rejects path-traversal names.
    """
    if not filename:
        return "dataset"
    name = os.path.basename(filename.replace("\\", "/"))
    if name in ("", ".", ".."):
        return "dataset"
    return name


class LocalStorageProvider:
    """Filesystem-backed storage under a configurable base directory."""

    def __init__(self, base_dir: str | os.PathLike[str]) -> None:
        self._root = Path(base_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # Generated keys look like datasets/<uuid>/versions/<n>/dataset.jsonl.
        # Defense in depth: reject any segment that could escape the root.
        if not key or key.startswith(("/", "\\")) or ".." in key.split("/"):
            raise InvalidDatasetSchemaError("Invalid storage key.")
        candidate = (self._root / key).resolve()
        try:
            candidate.relative_to(self._root.resolve())
        except ValueError:
            raise InvalidDatasetSchemaError("Invalid storage key.")
        return candidate

    def put(self, key: str, data: bytes) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.is_file():
            path.unlink()
