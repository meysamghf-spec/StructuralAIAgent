"""Application service - project memory operations."""

from __future__ import annotations

from uuid import UUID

from app.application.exceptions import ProjectNotFoundError
from app.domain.models.project_memory import MemoryType, ProjectMemory, ProjectMemoryContext
from app.domain.repositories.protocols import (
    ProjectMemoryRepository,
    ProjectRepository,
)


class ProjectMemoryService:
    def __init__(
        self,
        project_repository: ProjectRepository,
        memory_repository: ProjectMemoryRepository,
    ) -> None:
        self._projects = project_repository
        self._memory = memory_repository

    def create_memory(
        self,
        project_id: UUID,
        memory_type: MemoryType,
        content: str,
        *,
        source_type: str | None = None,
        source_id: UUID | None = None,
        confidence: float | None = None,
        metadata: dict | None = None,
        created_by: str | None = None,
    ) -> ProjectMemory:
        self._ensure_project_exists(project_id)

        return self._memory.create(
            project_id,
            memory_type,
            content,
            source_type=source_type,
            source_id=source_id,
            confidence=confidence,
            metadata=metadata,
            created_by=created_by,
        )

    def list_memories(
        self,
        project_id: UUID,
    ) -> list[ProjectMemory]:
        self._ensure_project_exists(project_id)
        return self._memory.list_for_project(project_id)

    def list_memories_by_type(
        self,
        project_id: UUID,
        memory_type: MemoryType,
    ) -> list[ProjectMemory]:
        self._ensure_project_exists(project_id)
        return self._memory.list_by_type(project_id, memory_type)

    def retrieve_memories(
        self,
        project_id: UUID,
        *,
        source_type: str | None = None,
        source_id: UUID | None = None,
        memory_type: MemoryType | None = None,
    ) -> list[ProjectMemory]:
        self._ensure_project_exists(project_id)
        return self._memory.search(
            project_id,
            source_type=source_type,
            source_id=source_id,
            memory_type=memory_type,
        )

    def get_project_context(self, project_id: UUID) -> ProjectMemoryContext:
        self._ensure_project_exists(project_id)
        memories = self._memory.list_for_project(project_id)
        counts_by_type: dict[str, int] = {}
        for memory in memories:
            key = memory.memory_type.value
            counts_by_type[key] = counts_by_type.get(key, 0) + 1
        return ProjectMemoryContext(
            project_id=project_id,
            memories=memories,
            total_count=len(memories),
            counts_by_type=counts_by_type,
        )

    def get_memory(
        self,
        project_id: UUID,
        memory_id: UUID,
    ) -> ProjectMemory | None:
        self._ensure_project_exists(project_id)
        return self._memory.get_by_id(project_id, memory_id)

    def delete_memory(
        self,
        project_id: UUID,
        memory_id: UUID,
    ) -> bool:
        self._ensure_project_exists(project_id)
        return self._memory.delete(project_id, memory_id)

    def _ensure_project_exists(self, project_id: UUID) -> None:
        if self._projects.get_by_id(project_id) is None:
            raise ProjectNotFoundError(project_id)
