"""Structural software integration domain models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class IntegrationSoftware(StrEnum):
    ETABS = "ETABS"
    SAP2000 = "SAP2000"
    SAFE = "SAFE"
    AUTOCAD = "AUTOCAD"


class IntegrationOperation(StrEnum):
    IMPORT_MODEL = "IMPORT_MODEL"
    EXPORT_MODEL = "EXPORT_MODEL"
    RUN_ANALYSIS = "RUN_ANALYSIS"
    EXTRACT_RESULTS = "EXTRACT_RESULTS"
    GENERATE_DRAWING = "GENERATE_DRAWING"
    EXPORT_DXF = "EXPORT_DXF"
    EXPORT_DWG = "EXPORT_DWG"
    STATUS = "STATUS"


class IntegrationOperationStatus(StrEnum):
    SUCCESS = "SUCCESS"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    FAILED = "FAILED"
    REQUIRES_LOCAL_SOFTWARE = "REQUIRES_LOCAL_SOFTWARE"


class IntegrationRequest(BaseModel):
    project_id: UUID
    software: IntegrationSoftware
    operation: IntegrationOperation
    parameters: dict[str, Any] = Field(default_factory=dict)


class IntegrationResult(BaseModel):
    software: IntegrationSoftware
    operation: IntegrationOperation
    status: IntegrationOperationStatus
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
