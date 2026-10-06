"""Meta-Agent API schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.meta_agent import (
    AgentBuildResult,
    AgentCapabilityMatch,
    AgentProposal,
    AgentProposalRegistrationResult,
    AgentSpecification,
    MetaAgentDecision,
    MetaAgentSpecificationSubmission,
)


class MetaAgentDecideRequest(BaseModel):
    user_request: str = Field(min_length=1, max_length=4096)
    project_id: UUID | None = None


class AgentCapabilityMatchResponse(BaseModel):
    agent_type: str
    agent_name: str
    confidence: float
    reason: str
    matched_capabilities: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, match: AgentCapabilityMatch) -> AgentCapabilityMatchResponse:
        return cls(
            agent_type=match.agent_type.value,
            agent_name=match.agent_name,
            confidence=match.confidence,
            reason=match.reason,
            matched_capabilities=list(match.matched_capabilities),
            matched_keywords=list(match.matched_keywords),
        )


class AgentSpecificationResponse(BaseModel):
    name: str
    purpose: str
    user_description: str
    required_capabilities: list[str]
    expected_inputs: list[str]
    expected_outputs: list[str]
    tools_required: list[str]
    authorization_requirements: list[str]
    safety_constraints: list[str]
    approval_required: bool
    version: str
    originating_user_request: str

    @classmethod
    def from_domain(cls, specification: AgentSpecification) -> AgentSpecificationResponse:
        return cls(
            name=specification.name,
            purpose=specification.purpose,
            user_description=specification.user_description,
            required_capabilities=list(specification.required_capabilities),
            expected_inputs=list(specification.expected_inputs),
            expected_outputs=list(specification.expected_outputs),
            tools_required=list(specification.tools_required),
            authorization_requirements=list(specification.authorization_requirements),
            safety_constraints=list(specification.safety_constraints),
            approval_required=specification.approval_required,
            version=specification.version,
            originating_user_request=specification.originating_user_request,
        )


class AgentProposalResponse(BaseModel):
    id: UUID | None = None
    status: str
    name: str
    purpose: str
    description: str
    domain: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    expected_inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    prompt_instructions: str | None = None
    tools_required: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    authorization_requirements: list[str] = Field(default_factory=list)
    data_access_requirements: list[str] = Field(default_factory=list)
    validation_requirements: list[str] = Field(default_factory=list)
    approval_required: bool
    version: str
    originating_user_request: str

    @classmethod
    def from_domain(cls, proposal: AgentProposal) -> AgentProposalResponse:
        return cls(
            id=proposal.id,
            status=proposal.status.value,
            name=proposal.name,
            purpose=proposal.purpose,
            description=proposal.description,
            domain=proposal.domain,
            required_capabilities=list(proposal.required_capabilities),
            expected_inputs=list(proposal.expected_inputs),
            expected_outputs=list(proposal.expected_outputs),
            prompt_instructions=proposal.prompt_instructions,
            tools_required=list(proposal.tools_required),
            dependencies=list(proposal.dependencies),
            authorization_requirements=list(proposal.authorization_requirements),
            data_access_requirements=list(proposal.data_access_requirements),
            validation_requirements=list(proposal.validation_requirements),
            approval_required=proposal.approval_required,
            version=proposal.version,
            originating_user_request=proposal.originating_user_request,
        )


class MetaAgentDecisionResponse(BaseModel):
    kind: str
    user_request: str
    matches: list[AgentCapabilityMatchResponse] = Field(default_factory=list)
    selected_agent_type: str | None = None
    proposal: AgentProposalResponse | None = None
    specification: AgentSpecificationResponse | None = None
    requires_new_agent: bool = False
    unsupported_reason: str | None = None
    discovery_reason: str | None = None

    @classmethod
    def from_domain(cls, decision: MetaAgentDecision) -> MetaAgentDecisionResponse:
        return cls(
            kind=decision.kind.value,
            user_request=decision.user_request,
            matches=[AgentCapabilityMatchResponse.from_domain(item) for item in decision.matches],
            selected_agent_type=(
                decision.selected_agent_type.value if decision.selected_agent_type is not None else None
            ),
            proposal=(
                AgentProposalResponse.from_domain(decision.proposal)
                if decision.proposal is not None
                else None
            ),
            specification=(
                AgentSpecificationResponse.from_domain(decision.specification)
                if decision.specification is not None
                else None
            ),
            requires_new_agent=decision.requires_new_agent,
            unsupported_reason=decision.unsupported_reason,
            discovery_reason=decision.discovery_reason,
        )


class SubmitAgentSpecificationRequest(BaseModel):
    project_id: UUID
    specification: AgentSpecification
    conversation_id: UUID | None = None


class AgentBuildResultResponse(BaseModel):
    status: str
    message: str
    approval_request_id: UUID | None = None

    @classmethod
    def from_domain(cls, result: AgentBuildResult) -> AgentBuildResultResponse:
        return cls(
            status=result.status.value,
            message=result.message,
            approval_request_id=result.approval_request_id,
        )


class MetaAgentSpecificationSubmissionResponse(BaseModel):
    approval_request_id: UUID
    specification: AgentSpecificationResponse
    proposal: AgentProposalResponse
    build_result: AgentBuildResultResponse
    conversation_message_id: UUID | None = None

    @classmethod
    def from_domain(
        cls,
        submission: MetaAgentSpecificationSubmission,
    ) -> MetaAgentSpecificationSubmissionResponse:
        assert submission.build_result is not None
        return cls(
            approval_request_id=submission.approval_request_id,
            specification=AgentSpecificationResponse.from_domain(submission.specification),
            proposal=AgentProposalResponse.from_domain(submission.proposal),
            build_result=AgentBuildResultResponse.from_domain(submission.build_result),
            conversation_message_id=submission.conversation_message_id,
        )


class AgentProposalRegistrationResponse(BaseModel):
    proposal_status: str
    agent_id: UUID
    agent_key: str
    version: int
    agent_definition_status: str
    agent_version_status: str
    message: str

    @classmethod
    def from_domain(cls, result: AgentProposalRegistrationResult) -> AgentProposalRegistrationResponse:
        return cls(
            proposal_status=result.proposal_status.value,
            agent_id=result.agent_id,
            agent_key=result.agent_key,
            version=result.version,
            agent_definition_status=result.agent_definition_status.value,
            agent_version_status=result.agent_version_status.value,
            message=result.message,
        )
