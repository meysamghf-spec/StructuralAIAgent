"""File storage contract — infrastructure implements local filesystem."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class FileStorageProtocol(Protocol):
    def store(
        self,
        project_id: UUID,
        file_id: UUID,
        content: bytes,
        *,
        extension: str,
    ) -> str: ...

    def retrieve(self, storage_path: str) -> bytes: ...

    def resolve_path(self, storage_path: str) -> str: ...
