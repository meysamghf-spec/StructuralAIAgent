"""Document indexing — link project files to project memory records.

Intended post-extraction integration point (not wired into upload yet):
after ``FileIngestionService.ingest_upload`` returns a ``ProjectFile`` with
``parsing_status`` and ``extraction_status`` both ``COMPLETE`` and successful
extraction metadata present, ``DocumentIndexingService.index_file`` may be invoked.
"""

from __future__ import annotations

from uuid import UUID

from app.application.exceptions import FileNotReadyForIndexingError
from app.application.file_registry_service import FileRegistryService
from app.application.project_memory_service import ProjectMemoryService
from app.application.traceability_integration import record_source_to_memory
from app.application.traceability_service import TraceabilityService
from app.domain.models.file_artifact import ExtractionStatus, ParsingStatus, ProjectFile
from app.domain.models.project_memory import (
    FILE_MEMORY_SOURCE_TYPE,
    MemoryType,
    ProjectMemory,
)


class DocumentIndexingService:
    def __init__(
        self,
        *,
        file_registry_service: FileRegistryService,
        memory_service: ProjectMemoryService,
        traceability_service: TraceabilityService | None = None,
    ) -> None:
        self._files = file_registry_service
        self._memory = memory_service
        self._traceability = traceability_service

    def is_ready_for_indexing(self, project_id: UUID, file_id: UUID) -> bool:
        file_record = self._files.get_project_file(project_id, file_id)
        return is_file_ready_for_indexing(file_record)

    def index_file(
        self,
        project_id: UUID,
        file_id: UUID,
        *,
        created_by: str | None = None,
    ) -> ProjectMemory:
        file_record = self._files.get_project_file(project_id, file_id)
        if not is_file_ready_for_indexing(file_record):
            raise FileNotReadyForIndexingError(
                project_id,
                file_id,
                reason=_indexing_block_reason(file_record),
            )

        extraction = file_record.metadata.get("extraction", {})
        stub_metadata = extraction.get("metadata", {}) if isinstance(extraction, dict) else {}

        memory = self._memory.create_memory(
            project_id,
            MemoryType.EXTRACTED_INFORMATION,
            _build_index_content(file_record, stub_metadata),
            source_type=FILE_MEMORY_SOURCE_TYPE,
            source_id=file_id,
            confidence=file_record.confidence,
            metadata={
                "filename": file_record.filename,
                "file_type": file_record.file_type.value,
                "file_version": file_record.file_version,
                "content_type": file_record.content_type,
                "extraction": extraction,
            },
            created_by=created_by or file_record.created_by,
        )
        if self._traceability is not None:
            record_source_to_memory(
                self._traceability,
                project_id=project_id,
                file_id=file_id,
                memory_id=memory.id,
                metadata={"filename": file_record.filename},
            )
        return memory

    def get_memories_for_file(
        self,
        project_id: UUID,
        file_id: UUID,
    ) -> list[ProjectMemory]:
        self._files.get_project_file(project_id, file_id)
        return self._memory.retrieve_memories(
            project_id,
            source_type=FILE_MEMORY_SOURCE_TYPE,
            source_id=file_id,
        )


def is_file_ready_for_indexing(file_record: ProjectFile) -> bool:
    if file_record.parsing_status != ParsingStatus.COMPLETE:
        return False
    if file_record.extraction_status != ExtractionStatus.COMPLETE:
        return False
    extraction = file_record.metadata.get("extraction")
    if not isinstance(extraction, dict):
        return False
    return extraction.get("success") is True


def _indexing_block_reason(file_record: ProjectFile) -> str:
    if file_record.parsing_status != ParsingStatus.COMPLETE:
        return f"parsing_status is {file_record.parsing_status.value}"
    if file_record.extraction_status != ExtractionStatus.COMPLETE:
        return f"extraction_status is {file_record.extraction_status.value}"
    extraction = file_record.metadata.get("extraction")
    if not isinstance(extraction, dict) or extraction.get("success") is not True:
        return "extraction did not complete successfully"
    return "unknown"


def _build_index_content(file_record: ProjectFile, stub_metadata: dict) -> str:
    line_count = stub_metadata.get("line_count")
    if line_count is not None:
        return f"Document '{file_record.filename}' indexed ({line_count} lines)."
    return f"Document '{file_record.filename}' indexed."
