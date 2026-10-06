"""Build project-scoped, agent-facing context for chat file attachments."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from app.application.document_extraction_service import (
    build_agent_preview,
    document_from_file_record,
    limitation_from_document,
)
from app.application.document_indexing_service import DocumentIndexingService
from app.application.file_ingestion_service import FileIngestionService
from app.application.file_registry_service import FileRegistryService
from app.domain.models.file_artifact import ExtractionStatus, FileType, ParsingStatus, ProjectFile

AVAILABILITY_INDEXED = "indexed"
AVAILABILITY_EXTRACTED = "extracted"
AVAILABILITY_STORED_ONLY = "stored_only"
AVAILABILITY_FAILED = "failed"

_EXTENSION_LIMITATIONS: dict[str, str] = {
    ".doc": "Legacy Word .doc extraction is not implemented. The file is stored for reference only.",
    ".png": "Image OCR is not available in this environment. The image is stored for reference only.",
    ".jpg": "Image OCR is not available in this environment. The image is stored for reference only.",
    ".jpeg": "Image OCR is not available in this environment. The image is stored for reference only.",
    ".gif": "Image OCR is not available in this environment. The image is stored for reference only.",
    ".webp": "Image OCR is not available in this environment. The image is stored for reference only.",
    ".edb": (
        "ETABS EDB is a proprietary binary model database. Automated content extraction is not "
        "implemented. The file is stored for reference; use the ETABS integration workflow."
    ),
    ".sdb": (
        "SAP2000 SDB is a proprietary binary model database. Automated content extraction is not "
        "implemented. The file is stored for reference; use the SAP2000 integration workflow."
    ),
    ".f2k": (
        "SAP2000 F2K export is stored, but structured model parsing is not implemented. "
        "Use the SAP2000 integration workflow."
    ),
    ".dwg": (
        "AutoCAD DWG is a binary CAD format. Automated geometry extraction is not implemented. "
        "Use the CAD integration workflow."
    ),
    ".dxf": (
        "DXF geometry extraction is not implemented. The file is stored for reference; "
        "use the CAD integration workflow."
    ),
}


@dataclass
class AttachmentContextEntry:
    file_id: str
    filename: str
    file_type: str
    content_type: str | None
    availability: str
    parsing_status: str
    extraction_status: str
    limitation: str | None = None
    extraction_metadata: dict[str, Any] | None = None
    indexed_memory_ids: list[str] = field(default_factory=list)
    indexed_memory_content: list[str] = field(default_factory=list)
    text_preview: str | None = None
    structured_preview: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    byte_length: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "file_id": self.file_id,
            "filename": self.filename,
            "file_type": self.file_type,
            "content_type": self.content_type,
            "availability": self.availability,
            "parsing_status": self.parsing_status,
            "extraction_status": self.extraction_status,
        }
        if self.limitation:
            payload["limitation"] = self.limitation
        if self.extraction_metadata:
            payload["extraction_metadata"] = self.extraction_metadata
        if self.indexed_memory_ids:
            payload["indexed_memory_ids"] = self.indexed_memory_ids
        if self.indexed_memory_content:
            payload["indexed_memory_content"] = self.indexed_memory_content
        if self.text_preview:
            payload["text_preview"] = self.text_preview
        if self.structured_preview:
            payload["structured_preview"] = self.structured_preview
        if self.warnings:
            payload["warnings"] = self.warnings
        if self.byte_length is not None:
            payload["byte_length"] = self.byte_length
        return payload


@dataclass
class ChatAttachmentContextBundle:
    entries: list[AttachmentContextEntry] = field(default_factory=list)

    @property
    def file_ids(self) -> list[str]:
        return [entry.file_id for entry in self.entries]

    def to_dict(self) -> dict[str, Any]:
        return {"attachments": [entry.to_dict() for entry in self.entries]}

    def to_metadata(self) -> dict[str, Any]:
        return {
            "attachment_context": self.to_dict(),
            "attachment_file_ids": self.file_ids,
        }

    def to_prompt_section(self) -> str:
        if not self.entries:
            return ""
        lines = ["", "Attached files (engineering context):"]
        for entry in self.entries:
            label = entry.file_type or entry.content_type or "file"
            lines.append(f"\n### {entry.filename} ({label}, id={entry.file_id})")
            lines.append(f"Availability: {entry.availability}")
            lines.append(f"Parsing: {entry.parsing_status}; Extraction: {entry.extraction_status}")
            if entry.byte_length is not None:
                lines.append(f"Stored size: {entry.byte_length} bytes")
            if entry.extraction_metadata:
                meta_bits = []
                for key in ("line_count", "byte_length", "page_count", "paragraph_count", "sheet_count"):
                    value = entry.extraction_metadata.get(key)
                    if value is not None:
                        meta_bits.append(f"{key}={value}")
                if meta_bits:
                    lines.append(f"Extraction metadata: {', '.join(meta_bits)}")
            for warning in entry.warnings:
                lines.append(f"Warning: {warning}")
            for memory_content in entry.indexed_memory_content:
                lines.append(f"Indexed memory: {memory_content}")
            if entry.text_preview:
                lines.append("Extracted content:")
                lines.append(entry.text_preview)
            if entry.limitation:
                lines.append(f"Limitation: {entry.limitation}")
        return "\n".join(lines)


class ChatAttachmentContextService:
    def __init__(
        self,
        *,
        file_registry: FileRegistryService,
        file_ingestion: FileIngestionService,
        document_indexing: DocumentIndexingService,
    ) -> None:
        self._file_registry = file_registry
        self._file_ingestion = file_ingestion
        self._document_indexing = document_indexing

    def build(
        self,
        project_id: UUID,
        file_ids: list[UUID],
        *,
        created_by: str | None = None,
    ) -> ChatAttachmentContextBundle:
        entries: list[AttachmentContextEntry] = []
        for file_id in file_ids:
            record = self._file_registry.get_project_file(project_id, file_id)
            entries.append(self._build_entry(project_id, record, created_by=created_by))
        return ChatAttachmentContextBundle(entries=entries)

    def _build_entry(
        self,
        project_id: UUID,
        record: ProjectFile,
        *,
        created_by: str | None,
    ) -> AttachmentContextEntry:
        document = document_from_file_record(record)
        extraction = record.metadata.get("extraction")
        extraction_metadata = _extraction_metadata(record, document)
        byte_length = _byte_length(record)

        if record.parsing_status == ParsingStatus.FAILED or record.extraction_status == ExtractionStatus.FAILED:
            error_message = None
            if isinstance(extraction, dict):
                error_message = extraction.get("error_message")
            return AttachmentContextEntry(
                file_id=str(record.id),
                filename=record.filename,
                file_type=record.file_type.value,
                content_type=record.content_type,
                availability=AVAILABILITY_FAILED,
                parsing_status=record.parsing_status.value,
                extraction_status=record.extraction_status.value,
                limitation=limitation_from_document(document)
                or error_message
                or "File ingestion or extraction failed.",
                extraction_metadata=extraction_metadata,
                warnings=list(document.warnings) if document else [],
                byte_length=byte_length,
            )

        if document is not None and document.is_usable:
            return self._build_extracted_entry(
                project_id,
                record,
                document=document,
                extraction_metadata=extraction_metadata,
                created_by=created_by,
                byte_length=byte_length,
            )

        if record.file_type == FileType.TEXT and record.extraction_status == ExtractionStatus.COMPLETE:
            return self._build_legacy_text_entry(
                project_id,
                record,
                extraction_metadata=extraction_metadata,
                created_by=created_by,
                byte_length=byte_length,
            )

        limitation = _limitation_for_record(record, document)
        return AttachmentContextEntry(
            file_id=str(record.id),
            filename=record.filename,
            file_type=record.file_type.value,
            content_type=record.content_type,
            availability=AVAILABILITY_STORED_ONLY,
            parsing_status=record.parsing_status.value,
            extraction_status=record.extraction_status.value,
            limitation=limitation,
            byte_length=byte_length,
        )

    def _build_extracted_entry(
        self,
        project_id: UUID,
        record: ProjectFile,
        *,
        document,
        extraction_metadata: dict[str, Any] | None,
        created_by: str | None,
        byte_length: int | None,
    ) -> AttachmentContextEntry:
        memories = self._document_indexing.get_memories_for_file(project_id, record.id)
        if not memories and self._document_indexing.is_ready_for_indexing(project_id, record.id):
            memory = self._document_indexing.index_file(
                project_id,
                record.id,
                created_by=created_by or record.created_by,
            )
            memories = [memory]

        preview = build_agent_preview(document)
        availability = AVAILABILITY_INDEXED if memories else AVAILABILITY_EXTRACTED
        structured_preview = None
        structured = document.structured_data or {}
        if structured.get("sheets"):
            structured_preview = {"sheets": structured.get("sheets")}
        elif structured.get("pages"):
            structured_preview = {
                "page_count": structured.get("page_count"),
                "pages": [
                    {"page_number": page.get("page_number"), "text_length": len(page.get("text") or "")}
                    for page in structured.get("pages", [])
                    if isinstance(page, dict)
                ],
            }

        return AttachmentContextEntry(
            file_id=str(record.id),
            filename=record.filename,
            file_type=record.file_type.value,
            content_type=record.content_type,
            availability=availability,
            parsing_status=record.parsing_status.value,
            extraction_status=record.extraction_status.value,
            extraction_metadata=extraction_metadata,
            indexed_memory_ids=[str(memory.id) for memory in memories],
            indexed_memory_content=[memory.content for memory in memories[:3]],
            text_preview=preview,
            structured_preview=structured_preview,
            warnings=list(document.warnings),
            byte_length=byte_length,
        )

    def _build_legacy_text_entry(
        self,
        project_id: UUID,
        record: ProjectFile,
        *,
        extraction_metadata: dict[str, Any] | None,
        created_by: str | None,
        byte_length: int | None,
    ) -> AttachmentContextEntry:
        memories = self._document_indexing.get_memories_for_file(project_id, record.id)
        if not memories and self._document_indexing.is_ready_for_indexing(project_id, record.id):
            memory = self._document_indexing.index_file(
                project_id,
                record.id,
                created_by=created_by or record.created_by,
            )
            memories = [memory]

        text_preview = self._read_raw_text_preview(project_id, record.id)
        availability = AVAILABILITY_INDEXED if memories else AVAILABILITY_EXTRACTED
        return AttachmentContextEntry(
            file_id=str(record.id),
            filename=record.filename,
            file_type=record.file_type.value,
            content_type=record.content_type,
            availability=availability,
            parsing_status=record.parsing_status.value,
            extraction_status=record.extraction_status.value,
            extraction_metadata=extraction_metadata,
            indexed_memory_ids=[str(memory.id) for memory in memories],
            indexed_memory_content=[memory.content for memory in memories[:3]],
            text_preview=text_preview,
            byte_length=byte_length,
        )

    def _read_raw_text_preview(self, project_id: UUID, file_id: UUID) -> str | None:
        try:
            _, content = self._file_ingestion.get_file_content(project_id, file_id)
        except Exception:
            return None
        text = content.decode("utf-8", errors="replace")
        if len(text) <= 8000:
            return text
        return f"{text[:8000]}\n...[truncated]"


def _extraction_metadata(record: ProjectFile, document) -> dict[str, Any] | None:
    if document is not None and document.metadata:
        return dict(document.metadata)
    extraction = record.metadata.get("extraction")
    if isinstance(extraction, dict):
        raw_metadata = extraction.get("metadata")
        if isinstance(raw_metadata, dict):
            filtered = {key: value for key, value in raw_metadata.items() if key != "document"}
            return filtered or None
    return None


def _byte_length(record: ProjectFile) -> int | None:
    ingestion = record.metadata.get("ingestion")
    if isinstance(ingestion, dict):
        raw_length = ingestion.get("byte_length")
        if isinstance(raw_length, int):
            return raw_length
    document = document_from_file_record(record)
    if document and isinstance(document.metadata.get("byte_length"), int):
        return document.metadata["byte_length"]
    return None


def _limitation_for_record(record: ProjectFile, document) -> str:
    limitation = limitation_from_document(document)
    if limitation:
        return limitation
    extension = Path(record.filename).suffix.lower()
    if extension in _EXTENSION_LIMITATIONS:
        return _EXTENSION_LIMITATIONS[extension]
    ingestion = record.metadata.get("ingestion")
    if isinstance(ingestion, dict):
        note = ingestion.get("note")
        if isinstance(note, str) and note.strip():
            return note
    return (
        "Automated content extraction is not available for this file format. "
        "The file is stored for reference only."
    )


def enrich_user_request_with_attachments(
    content: str,
    attachments: list[Any],
    bundle: ChatAttachmentContextBundle | None,
) -> str:
    if not attachments:
        return content
    if bundle is not None and bundle.entries:
        return content + bundle.to_prompt_section()

    lines = [content, "", "Attached files:"]
    for attachment in attachments:
        label = getattr(attachment, "file_type", None) or getattr(attachment, "content_type", None) or "file"
        filename = getattr(attachment, "filename", "unknown")
        file_id = getattr(attachment, "file_id", "unknown")
        lines.append(f"- {filename} ({label}, id={file_id})")
    return "\n".join(lines)
