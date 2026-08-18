"""CodeEngine domain models — deterministic code checks and configuration validation."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.domain.models.pem import CodeConfiguration, Jurisdiction


class StandardRole(StrEnum):
    BUILDING_CODE = "BUILDING_CODE"
    LOADING = "LOADING"
    SEISMIC = "SEISMIC"
    CONCRETE = "CONCRETE"
    STEEL = "STEEL"
    FOUNDATION = "FOUNDATION"
    SUPPLEMENTARY = "SUPPLEMENTARY"


class ProvisionStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    PROVISION_TEXT_UNAVAILABLE = "PROVISION_TEXT_UNAVAILABLE"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class CheckOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    REQUIRES_ENGINEER_REVIEW = "REQUIRES_ENGINEER_REVIEW"


class StandardInfo(BaseModel):
    plugin_id: str
    family: str
    edition: str
    full_designation: str
    roles: list[StandardRole] = Field(default_factory=list)


class ProvisionReference(BaseModel):
    plugin_id: str
    section_ref: str
    status: ProvisionStatus = ProvisionStatus.PROVISION_TEXT_UNAVAILABLE
    summary: str | None = None


class CodeCheckResult(BaseModel):
    check_id: str
    outcome: CheckOutcome
    message: str
    code_family: str | None = None
    code_edition: str | None = None
    code_section: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodeConflictReport(BaseModel):
    conflict_type: str
    severity: str
    message: str
    affected_standards: list[str] = Field(default_factory=list)
    recommendation: str | None = None


class CodeConfigurationValidationResult(BaseModel):
    is_valid: bool
    configuration: CodeConfiguration
    conflicts: list[CodeConflictReport] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CodeDefaultsResult(BaseModel):
    jurisdiction: Jurisdiction
    configuration: CodeConfiguration
