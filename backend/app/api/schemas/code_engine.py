"""CodeEngine API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.models.code_engine import (
    CodeCheckResult,
    CodeConfigurationValidationResult,
    CodeDefaultsResult,
    StandardInfo,
)
from app.domain.models.pem import CodeConfiguration, Jurisdiction


class StandardInfoResponse(BaseModel):
    plugin_id: str
    family: str
    edition: str
    full_designation: str
    roles: list[str]

    @classmethod
    def from_domain(cls, info: StandardInfo) -> StandardInfoResponse:
        return cls(
            plugin_id=info.plugin_id,
            family=info.family,
            edition=info.edition,
            full_designation=info.full_designation,
            roles=[role.value for role in info.roles],
        )


class CodeDefaultsResponse(BaseModel):
    jurisdiction: Jurisdiction
    configuration: CodeConfiguration


class ValidateCodeConfigurationRequest(BaseModel):
    configuration: CodeConfiguration


class CodeConflictResponse(BaseModel):
    conflict_type: str
    severity: str
    message: str
    affected_standards: list[str] = Field(default_factory=list)
    recommendation: str | None = None


class CodeConfigurationValidationResponse(BaseModel):
    is_valid: bool
    configuration: CodeConfiguration
    conflicts: list[CodeConflictResponse]
    warnings: list[str]

    @classmethod
    def from_domain(
        cls, result: CodeConfigurationValidationResult
    ) -> CodeConfigurationValidationResponse:
        return cls(
            is_valid=result.is_valid,
            configuration=result.configuration,
            conflicts=[
                CodeConflictResponse.model_validate(conflict.model_dump())
                for conflict in result.conflicts
            ],
            warnings=result.warnings,
        )


class CodeDefaultsEnvelopeResponse(BaseModel):
    jurisdiction: Jurisdiction
    configuration: CodeConfiguration

    @classmethod
    def from_domain(cls, result: CodeDefaultsResult) -> CodeDefaultsEnvelopeResponse:
        return cls(jurisdiction=result.jurisdiction, configuration=result.configuration)


class RunCodeCheckRequest(BaseModel):
    plugin_id: str
    check_id: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    code_configuration: CodeConfiguration


class CodeCheckResponse(BaseModel):
    check_id: str
    outcome: str
    message: str
    code_family: str | None = None
    code_edition: str | None = None
    code_section: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, result: CodeCheckResult) -> CodeCheckResponse:
        return cls(
            check_id=result.check_id,
            outcome=result.outcome.value,
            message=result.message,
            code_family=result.code_family,
            code_edition=result.code_edition,
            code_section=result.code_section,
            inputs=result.inputs,
        )
