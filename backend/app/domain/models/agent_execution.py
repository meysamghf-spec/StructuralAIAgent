"""AgentExecution contract — re-export runtime models for backward compatibility."""

from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import (
    AgentExecution,
    AgentExecutionRecord,
    AgentExecutionRequest,
    AgentExecutionStatus,
    AgentResult,
    AgentValidationStatus,
    PromptGenerationResult,
)

__all__ = [
    "AgentExecution",
    "AgentExecutionRecord",
    "AgentExecutionRequest",
    "AgentExecutionStatus",
    "AgentResult",
    "AgentValidationStatus",
    "EngineeringAgentType",
    "PromptGenerationResult",
]
