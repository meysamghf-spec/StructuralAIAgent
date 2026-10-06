"""Shared parser helpers for normalized document extraction."""

from __future__ import annotations

from app.domain.models.document_extraction import DocumentExtractionResult, DocumentExtractionStatus
from app.domain.models.ingestion import ExtractionResult


def extraction_from_document(
    document: DocumentExtractionResult,
    *,
    parser_key: str,
    confidence: float | None = None,
    error_message: str | None = None,
) -> ExtractionResult:
    success = document.status in {
        DocumentExtractionStatus.SUCCESS,
        DocumentExtractionStatus.PARTIAL,
    }
    return ExtractionResult(
        parser_key=parser_key,
        success=success,
        confidence=confidence if confidence is not None else (1.0 if success else None),
        metadata={"document": document.model_dump(mode="json")},
        error_message=error_message,
    )
