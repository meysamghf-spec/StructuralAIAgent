"""Safe stub Agent Builder port — records requests without faking code generation."""

from __future__ import annotations

from uuid import UUID

from app.domain.models.meta_agent import AgentBuildResult, AgentBuildStatus, AgentSpecification


class StubAgentBuilderPort:
    """Records approved build requests until a real Cursor integration is configured."""

    def submit_build(
        self,
        specification: AgentSpecification,
        *,
        approval_request_id: UUID,
        project_id: UUID | None,
        requested_by: str,
    ) -> AgentBuildResult:
        return AgentBuildResult(
            status=AgentBuildStatus.UNAVAILABLE,
            message=(
                "Cursor Agent Builder integration is not configured in this environment. "
                "The approved specification was recorded but no code was generated."
            ),
            specification=specification,
            approval_request_id=approval_request_id,
            metadata={
                "project_id": str(project_id) if project_id is not None else None,
                "requested_by": requested_by,
                "integration": "stub",
                "build_started": False,
                "build_completed": False,
            },
        )
