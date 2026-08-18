"""Local filesystem storage adapter — keeps files outside the source tree."""

from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID

from app.application.exceptions import FileStorageError

_SAFE_EXTENSION = re.compile(r"^[a-z0-9]{1,16}$")


class LocalFileStorage:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def store(
        self,
        project_id: UUID,
        file_id: UUID,
        content: bytes,
        *,
        extension: str,
    ) -> str:
        normalized_extension = extension.lower().lstrip(".")
        if not _SAFE_EXTENSION.match(normalized_extension):
            raise FileStorageError("Invalid storage extension")

        relative = f"{project_id}/{file_id}.{normalized_extension}"
        self._assert_safe_relative_path(relative)
        destination = (self._root / relative).resolve()
        if not str(destination).startswith(str(self._root)):
            raise FileStorageError("Resolved storage path escapes configured root")

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return relative

    def retrieve(self, storage_path: str) -> bytes:
        path = self._resolve_under_root(storage_path)
        if not path.is_file():
            raise FileStorageError("Stored file not found")
        return path.read_bytes()

    def resolve_path(self, storage_path: str) -> str:
        return str(self._resolve_under_root(storage_path))

    def _resolve_under_root(self, storage_path: str) -> Path:
        self._assert_safe_relative_path(storage_path)
        resolved = (self._root / storage_path).resolve()
        if not str(resolved).startswith(str(self._root)):
            raise FileStorageError("Storage path traversal rejected")
        return resolved

    @staticmethod
    def _assert_safe_relative_path(storage_path: str) -> None:
        if not storage_path or storage_path.startswith(("/", "\\")):
            raise FileStorageError("Storage path must be relative")
        parts = Path(storage_path).parts
        if any(part in ("..", "") for part in parts):
            raise FileStorageError("Storage path traversal rejected")
