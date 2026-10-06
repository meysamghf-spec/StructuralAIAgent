"""Agent Builder port — boundary for future Cursor / external builder integrations."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.models.meta_agent import AgentBuildResult, AgentSpecification


class AgentBuilderPort(Protocol):
    """Submit approved agent specifications for external implementation."""

    def submit_build(
        self,
        specification: AgentSpecification,
        *,
        approval_request_id: UUID,
        project_id: UUID | None,
        requested_by: str,
    ) -> AgentBuildResult: ...
