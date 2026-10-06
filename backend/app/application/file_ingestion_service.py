"""Synchronous upload and ingestion orchestration for project files."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from app.application.exceptions import (
    ParserNotFoundError,
    ProjectFileNotFoundError,
    ProjectNotFoundError,
)
from app.application.document_indexing_service import (
    DocumentIndexingService,
    is_file_ready_for_indexing,
)
from app.application.file_type_detection import detect_file_type
from app.application.project_service import ProjectService
from app.application.upload_validation import validate_filename, validate_upload_size
from app.domain.contracts.file_parser import FileParserProtocol
from app.domain.contracts.file_storage import FileStorageProtocol
from app.domain.models.file_artifact import (
    ExtractionStatus,
    FileSource,
    FileType,
    ParsingStatus,
    ProjectFile,
)
from app.domain.repositories.file_protocols import ProjectFileRepository


class FileIngestionService:
    def __init__(
        self,
        *,
        project_service: ProjectService,
        file_repository: ProjectFileRepository,
        file_storage: FileStorageProtocol,
        parsers: list[FileParserProtocol],
        max_upload_bytes: int,
        document_indexing_service: DocumentIndexingService | None = None,
        auto_index_on_extraction: bool = False,
    ) -> None:
        self._project_service = project_service
        self._file_repository = file_repository
        self._file_storage = file_storage
        self._parsers = parsers
        self._max_upload_bytes = max_upload_bytes
        self._document_indexing = document_indexing_service
        self._auto_index_on_extraction = auto_index_on_extraction

    def ingest_upload(
        self,
        project_id: UUID,
        *,
        filename: str,
        content: bytes,
        content_type: str | None,
        created_by: str | None,
    ) -> ProjectFile:
        if self._project_service.get_project(project_id) is None:
            raise ProjectNotFoundError(project_id)

        safe_filename = validate_filename(filename)
        validate_upload_size(content, max_bytes=self._max_upload_bytes)
        detection = detect_file_type(safe_filename, content_type)

        file_id = uuid4()
        extension = Path(safe_filename).suffix.lower().lstrip(".")
        storage_path = self._file_storage.store(
            project_id,
            file_id,
            content,
            extension=extension,
        )

        record = self._file_repository.create(
            file_id=file_id,
            project_id=project_id,
            filename=safe_filename,
            content_type=detection.content_type,
            file_type=detection.file_type,
            file_version=None,
            source=FileSource.USER_UPLOAD,
            storage_path=storage_path,
            parsing_status=ParsingStatus.PENDING,
            extraction_status=ExtractionStatus.PENDING,
            confidence=None,
            metadata={"detection": detection.model_dump()},
            created_by=created_by,
        )

        return self._run_ingestion(project_id, record.id, content)

    def get_file_content(self, project_id: UUID, file_id: UUID) -> tuple[ProjectFile, bytes]:
        record = self._file_repository.get_by_id(project_id, file_id)
        if record is None:
            if self._project_service.get_project(project_id) is None:
                raise ProjectNotFoundError(project_id)
            raise ProjectFileNotFoundError(project_id, file_id)
        content = self._file_storage.retrieve(record.storage_path)
        return record, content

    def _run_ingestion(self, project_id: UUID, file_id: UUID, content: bytes) -> ProjectFile:
        record = self._file_repository.get_by_id(project_id, file_id)
        if record is None:
            raise ProjectFileNotFoundError(project_id, file_id)

        if record.file_type in {FileType.UNKNOWN, FileType.IMAGE}:
            metadata = dict(record.metadata)
            metadata["ingestion"] = {
                "stored": True,
                "byte_length": len(content),
                "note": _skip_extraction_note(record),
            }
            return self._require_updated(
                self._file_repository.update_statuses(
                    project_id,
                    file_id,
                    parsing_status=ParsingStatus.SKIPPED,
                    extraction_status=ExtractionStatus.SKIPPED,
                    confidence=None,
                    metadata=metadata,
                ),
                project_id,
                file_id,
            )

        self._file_repository.update_statuses(
            project_id,
            file_id,
            parsing_status=ParsingStatus.IN_PROGRESS,
            extraction_status=ExtractionStatus.IN_PROGRESS,
        )

        parser = self._select_parser(record.file_type, record.content_type)
        extraction = parser.extract(content, filename=record.filename)

        metadata = dict(record.metadata)
        metadata["extraction"] = extraction.model_dump()

        if extraction.success:
            record = self._require_updated(
                self._file_repository.update_statuses(
                    project_id,
                    file_id,
                    parsing_status=ParsingStatus.COMPLETE,
                    extraction_status=ExtractionStatus.COMPLETE,
                    confidence=extraction.confidence,
                    metadata=metadata,
                ),
                project_id,
                file_id,
            )
            return self._maybe_auto_index(project_id, record)

        metadata["extraction_error"] = extraction.error_message
        return self._require_updated(
            self._file_repository.update_statuses(
                project_id,
                file_id,
                parsing_status=ParsingStatus.FAILED,
                extraction_status=ExtractionStatus.FAILED,
                confidence=extraction.confidence,
                metadata=metadata,
            ),
            project_id,
            file_id,
        )

    def _select_parser(self, file_type, content_type: str | None) -> FileParserProtocol:
        for parser in self._parsers:
            if parser.supports(file_type, content_type):
                return parser
        raise ParserNotFoundError(file_type=str(file_type))

    def _maybe_auto_index(self, project_id: UUID, record: ProjectFile) -> ProjectFile:
        if (
            self._auto_index_on_extraction
            and self._document_indexing is not None
            and is_file_ready_for_indexing(record)
        ):
            self._document_indexing.index_file(
                project_id,
                record.id,
                created_by=record.created_by,
            )
        return record

    @staticmethod
    def _require_updated(
        record: ProjectFile | None,
        project_id: UUID,
        file_id: UUID,
    ) -> ProjectFile:
        if record is None:
            raise ProjectFileNotFoundError(project_id, file_id)
        return record


def _skip_extraction_note(record: ProjectFile) -> str:
    if record.file_type == FileType.IMAGE:
        return "Image stored; OCR is not available in this environment."
    extension = Path(record.filename).suffix.lower()
    notes = {
        ".edb": (
            "ETABS EDB stored; automated binary extraction is not implemented. "
            "Use the ETABS integration workflow."
        ),
        ".sdb": (
            "SAP2000 SDB stored; automated binary extraction is not implemented. "
            "Use the SAP2000 integration workflow."
        ),
        ".f2k": (
            "SAP2000 F2K stored; structured model parsing is not implemented. "
            "Use the SAP2000 integration workflow."
        ),
        ".dwg": (
            "DWG stored; automated geometry extraction is not implemented. "
            "Use the CAD integration workflow."
        ),
        ".dxf": (
            "DXF stored; automated geometry extraction is not implemented. "
            "Use the CAD integration workflow."
        ),
        ".doc": "Legacy Word .doc extraction is not implemented.",
    }
    return notes.get(
        extension,
        "Engineering file stored; automated extraction was not run for this format.",
    )
