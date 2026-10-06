"""Meta-Agent domain models — capability discovery and new-agent proposals."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.agent import AgentDefinitionStatus, AgentVersionStatus, EngineeringAgentType


class MetaAgentDecisionKind(StrEnum):
    ROUTE_TO_EXISTING_AGENT = "route_to_existing_agent"
    CREATE_NEW_AGENT = "create_new_agent"
    UNSUPPORTED = "unsupported"


class AgentProposalStatus(StrEnum):
    DRAFT = "draft"
    VALIDATING = "validating"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
    DISABLED = "disabled"


class AgentCapabilityMatch(BaseModel):
    agent_type: EngineeringAgentType
    agent_name: str
    confidence: float
    reason: str
    matched_capabilities: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)


class AgentSpecification(BaseModel):
    """Backward-compatible specification view derived from an AgentProposal."""

    name: str
    purpose: str
    user_description: str
    required_capabilities: list[str] = Field(default_factory=list)
    expected_inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    tools_required: list[str] = Field(default_factory=list)
    authorization_requirements: list[str] = Field(default_factory=list)
    safety_constraints: list[str] = Field(default_factory=list)
    approval_required: bool = True
    version: str = "0.1.0-draft"
    originating_user_request: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentProposal(BaseModel):
    id: UUID | None = None
    status: AgentProposalStatus = AgentProposalStatus.DRAFT
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
    approval_required: bool = True
    version: str = "0.1.0-draft"
    originating_user_request: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_specification(self) -> AgentSpecification:
        return AgentSpecification(
            name=self.name,
            purpose=self.purpose,
            user_description=self.description,
            required_capabilities=list(self.required_capabilities),
            expected_inputs=list(self.expected_inputs),
            expected_outputs=list(self.expected_outputs),
            tools_required=list(self.tools_required),
            authorization_requirements=list(self.authorization_requirements),
            safety_constraints=list(self.validation_requirements),
            approval_required=True,
            version=self.version,
            originating_user_request=self.originating_user_request,
            metadata={
                **self.metadata,
                "domain": self.domain,
                "proposal_id": str(self.id) if self.id is not None else None,
                "proposal_status": self.status.value,
            },
        )

    @classmethod
    def from_specification(cls, specification: AgentSpecification) -> AgentProposal:
        domain = specification.metadata.get("domain") if specification.metadata else None
        proposal_id_raw = specification.metadata.get("proposal_id") if specification.metadata else None
        proposal_id = UUID(proposal_id_raw) if isinstance(proposal_id_raw, str) else None
        status_raw = specification.metadata.get("proposal_status") if specification.metadata else None
        status = (
            AgentProposalStatus(status_raw)
            if isinstance(status_raw, str)
            else AgentProposalStatus.DRAFT
        )
        return cls(
            id=proposal_id,
            status=status,
            name=specification.name,
            purpose=specification.purpose,
            description=specification.user_description,
            domain=domain if isinstance(domain, str) else None,
            required_capabilities=list(specification.required_capabilities),
            expected_inputs=list(specification.expected_inputs),
            expected_outputs=list(specification.expected_outputs),
            tools_required=list(specification.tools_required),
            authorization_requirements=list(specification.authorization_requirements),
            validation_requirements=list(specification.safety_constraints),
            approval_required=True,
            version=specification.version,
            originating_user_request=specification.originating_user_request,
            metadata=dict(specification.metadata),
        )


class MetaAgentDecision(BaseModel):
    kind: MetaAgentDecisionKind
    user_request: str
    matches: list[AgentCapabilityMatch] = Field(default_factory=list)
    selected_agent_type: EngineeringAgentType | None = None
    proposal: AgentProposal | None = None
    specification: AgentSpecification | None = None
    requires_new_agent: bool = False
    unsupported_reason: str | None = None
    discovery_reason: str | None = None


class AgentBuildStatus(StrEnum):
    NOT_STARTED = "not_started"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    BUILD_REQUESTED = "build_requested"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class AgentBuildResult(BaseModel):
    status: AgentBuildStatus
    message: str
    specification: AgentSpecification | None = None
    proposal: AgentProposal | None = None
    approval_request_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MetaAgentSpecificationSubmission(BaseModel):
    specification: AgentSpecification
    proposal: AgentProposal
    approval_request_id: UUID
    build_result: AgentBuildResult | None = None
    conversation_message_id: UUID | None = None


class AgentProposalRegistrationResult(BaseModel):
    proposal_status: AgentProposalStatus
    agent_id: UUID
    agent_key: str
    version: int
    agent_definition_status: AgentDefinitionStatus
    agent_version_status: AgentVersionStatus
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
