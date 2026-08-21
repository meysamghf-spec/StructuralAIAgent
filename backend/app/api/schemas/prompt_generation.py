"""Prompt generation API schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import PromptGenerationResult


class PlanAgentExecutionRequest(BaseModel):
    project_id: UUID
    user_request: str = Field(..., min_length=1)


class PromptGenerationResponse(BaseModel):
    selected_agent_type: EngineeringAgentType
    generated_prompt: str
    context_requirements: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    user_intent: str = ""
    engineering_objectives: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    relevant_context: dict[str, Any] = Field(default_factory=dict)
    deterministic_services: list[str] = Field(default_factory=list)
    execution_plan: list[dict[str, Any]] = Field(default_factory=list)
    preserved_constraints: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, result: PromptGenerationResult) -> PromptGenerationResponse:
        return cls.model_validate(result.model_dump())
