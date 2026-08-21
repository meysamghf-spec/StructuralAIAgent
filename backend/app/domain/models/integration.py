"""Structural software integration domain models."""

from __future__ import annotations

from datetime import datetime
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
    CONNECT = "CONNECT"
    DISCONNECT = "DISCONNECT"
    DETECT = "DETECT"
    GENERATE_DRAWING = "GENERATE_DRAWING"
    EXPORT_DXF = "EXPORT_DXF"
    EXPORT_DWG = "EXPORT_DWG"
    STATUS = "STATUS"


class IntegrationOperationStatus(StrEnum):
    SUCCESS = "SUCCESS"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    FAILED = "FAILED"
    REQUIRES_LOCAL_SOFTWARE = "REQUIRES_LOCAL_SOFTWARE"
    NOT_INSTALLED = "NOT_INSTALLED"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    NOT_ACCESSIBLE = "NOT_ACCESSIBLE"


class SoftwareAvailabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    NOT_INSTALLED = "NOT_INSTALLED"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    NOT_ACCESSIBLE = "NOT_ACCESSIBLE"
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


class SoftwareCapabilityReport(BaseModel):
    software: IntegrationSoftware
    expected_version: str
    availability: SoftwareAvailabilityStatus
    detected_version: str | None = None
    install_path: str | None = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntegrationExecution(BaseModel):
    id: UUID
    project_id: UUID
    software: IntegrationSoftware
    operation: IntegrationOperation
    status: IntegrationOperationStatus
    pem_snapshot_id: UUID | None = None
    pem_version: int | None = None
    analysis_run_id: UUID | None = None
    message: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ExternalModelExport(BaseModel):
    project_id: UUID
    pem_snapshot_id: UUID
    pem_version: int
    software: IntegrationSoftware
    software_version: str
    exported_at: datetime
    structural_model: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExternalAnalysisResults(BaseModel):
    software: IntegrationSoftware
    software_version: str
    project_id: UUID
    pem_snapshot_id: UUID
    pem_version: int
    analysis_run_id: UUID | None = None
    imported_at: datetime
    result_types_present: list[str] = Field(default_factory=list)
    results: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
