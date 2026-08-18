"""Analysis and design API schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.analysis import AnalysisRequest, AnalysisResult
from app.domain.models.design import DesignRequest, DesignResult


class AnalysisRequestBody(BaseModel):
    project_id: UUID
    analysis_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    def to_domain(self) -> AnalysisRequest:
        return AnalysisRequest(
            project_id=self.project_id,
            analysis_type=self.analysis_type,
            parameters=self.parameters,
        )


class AnalysisResultResponse(BaseModel):
    project_id: UUID
    analysis_type: str
    status: str
    message: str
    model_version_id: UUID | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, result: AnalysisResult) -> AnalysisResultResponse:
        return cls.model_validate(result.model_dump())


class DesignRequestBody(BaseModel):
    project_id: UUID
    design_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    def to_domain(self) -> DesignRequest:
        return DesignRequest(
            project_id=self.project_id,
            design_type=self.design_type,
            parameters=self.parameters,
        )


class DesignResultResponse(BaseModel):
    project_id: UUID
    design_type: str
    status: str
    message: str
    code_edition: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, result: DesignResult) -> DesignResultResponse:
        return cls.model_validate(result.model_dump())
