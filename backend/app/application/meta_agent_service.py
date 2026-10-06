"""Meta-Agent decision layer — optional structural-engineering agent proposal foundation."""

from __future__ import annotations

import re
from uuid import UUID, uuid4

from app.application.agent_builder_service import AgentBuilderService
from app.application.agent_capability_discovery_service import AgentCapabilityDiscoveryService
from app.application.agent_intent_routing import AGENT_INTENT_ROUTING, UNSUPPORTED_REQUEST_MAX_LENGTH
from app.application.exceptions import (
    ConversationForbiddenError,
    ConversationNotFoundError,
    MetaAgentApprovalRequiredError,
    MetaAgentUnsupportedRequestError,
)
from app.application.human_approval_service import HumanApprovalService
from app.application.project_access_service import ProjectAccessService
from app.domain.approval_policy import requires_approval_for_target
from app.domain.contracts.agent_builder_port import AgentBuilderPort
from app.domain.models.conversation import MessageRole
from app.domain.models.human_approval import ApprovalStatus, ApprovalTargetType
from app.domain.models.meta_agent import (
    AgentBuildResult,
    AgentBuildStatus,
    AgentProposal,
    AgentProposalRegistrationResult,
    AgentProposalStatus,
    AgentSpecification,
    MetaAgentDecision,
    MetaAgentDecisionKind,
    MetaAgentSpecificationSubmission,
)
from app.domain.models.user import AuthenticatedAccount
from app.infrastructure.repositories.postgres_conversation_repository import (
    PostgresConversationRepository,
)

STRUCTURAL_ENGINEERING_DOMAIN = "structural_engineering"

_FORBIDDEN_SPEC_PATTERNS = (
    re.compile(r"\b(rm\s+-rf|sudo\s+|curl\s+.+\|\s*sh|wget\s+.+\|\s*sh)\b", re.IGNORECASE),
    re.compile(r"\b(os\.system|subprocess|eval\(|exec\()\b", re.IGNORECASE),
)

_STRUCTURAL_ENGINEERING_SCOPE_KEYWORDS: tuple[str, ...] = tuple(
    dict.fromkeys(
        keyword
        for keywords, _, _ in AGENT_INTENT_ROUTING
        for keyword in keywords
    )
) + (
    "structure",
    "structural",
    "engineering",
    "bridge",
    "building",
    "tower",
    "foundation",
    "corrosion",
    "etabs",
    "sap2000",
    "safe",
    "dwg",
    "dxf",
    "rebar",
    "prestress",
    "lateral",
    "frame",
    "truss",
    "civil",
    "construction",
)


class MetaAgentService:
    def __init__(
        self,
        *,
        discovery_service: AgentCapabilityDiscoveryService,
        project_access: ProjectAccessService,
        approval_service: HumanApprovalService,
        agent_builder: AgentBuilderPort,
        agent_registry_builder: AgentBuilderService,
        conversation_repository: PostgresConversationRepository,
    ) -> None:
        self._discovery = discovery_service
        self._project_access = project_access
        self._approval = approval_service
        self._agent_builder = agent_builder
        self._agent_registry_builder = agent_registry_builder
        self._conversation_repository = conversation_repository

    def decide(
        self,
        user_request: str,
        account: AuthenticatedAccount,
        *,
        project_id: UUID | None = None,
    ) -> MetaAgentDecision:
        if project_id is not None:
            self._project_access.require_project(project_id, account)

        trimmed = user_request.strip()
        if not trimmed:
            return MetaAgentDecision(
                kind=MetaAgentDecisionKind.UNSUPPORTED,
                user_request=user_request,
                unsupported_reason="A non-empty request is required.",
                discovery_reason="Empty request.",
            )
        if len(trimmed) > UNSUPPORTED_REQUEST_MAX_LENGTH:
            return MetaAgentDecision(
                kind=MetaAgentDecisionKind.UNSUPPORTED,
                user_request=user_request,
                unsupported_reason="Request exceeds the maximum supported length.",
                discovery_reason="Request too long.",
            )

        discovery = self._discovery.discover(trimmed, account, project_id=project_id)
        if discovery.requires_new_agent or discovery.best_match is None:
            if not self._is_structural_engineering_scoped(trimmed):
                return MetaAgentDecision(
                    kind=MetaAgentDecisionKind.UNSUPPORTED,
                    user_request=trimmed,
                    unsupported_reason=(
                        "Meta-Agent proposals are limited to structural-engineering agent creation."
                    ),
                    discovery_reason=discovery.reason,
                )
            proposal = self._build_proposal(trimmed)
            specification = proposal.to_specification()
            return MetaAgentDecision(
                kind=MetaAgentDecisionKind.CREATE_NEW_AGENT,
                user_request=trimmed,
                proposal=proposal,
                specification=specification,
                requires_new_agent=True,
                discovery_reason=discovery.reason,
            )

        return MetaAgentDecision(
            kind=MetaAgentDecisionKind.ROUTE_TO_EXISTING_AGENT,
            user_request=trimmed,
            matches=discovery.matches,
            selected_agent_type=discovery.best_match.agent_type,
            requires_new_agent=False,
            discovery_reason=discovery.reason,
        )

    def submit_specification_for_approval(
        self,
        specification: AgentSpecification,
        *,
        project_id: UUID,
        account: AuthenticatedAccount,
        actor_id: str,
        conversation_id: UUID | None = None,
    ) -> MetaAgentSpecificationSubmission:
        self._project_access.require_project(project_id, account)
        proposal = AgentProposal.from_specification(specification)
        proposal.status = AgentProposalStatus.VALIDATING
        proposal = self._sanitize_proposal(proposal)
        proposal.status = AgentProposalStatus.PENDING_APPROVAL
        sanitized_specification = proposal.to_specification()

        if not sanitized_specification.approval_required:
            raise MetaAgentApprovalRequiredError()

        if not requires_approval_for_target(ApprovalTargetType.AGENT_ACTION, "agent.create"):
            raise MetaAgentApprovalRequiredError(
                message="Server policy requires human approval before creating new agents.",
            )

        approval = self._approval.create_request(
            project_id,
            requester=actor_id,
            target_type=ApprovalTargetType.AGENT_ACTION,
            target_action="agent.create",
            summary=f"Create new agent: {proposal.name}",
            target_object_type="agent_proposal",
            metadata={
                "agent_proposal": proposal.model_dump(mode="json"),
                "agent_specification": sanitized_specification.model_dump(mode="json"),
                "requested_by_account": account.account_id,
            },
        )
        build_result = AgentBuildResult(
            status=AgentBuildStatus.PENDING_APPROVAL,
            message="Agent proposal submitted for human approval. Build has not started.",
            specification=sanitized_specification,
            proposal=proposal,
            approval_request_id=approval.id,
            metadata={"approval_status": approval.status.value, "proposal_status": proposal.status.value},
        )

        conversation_message_id: UUID | None = None
        if conversation_id is not None:
            message = self._record_proposal_provenance(
                conversation_id=conversation_id,
                account=account,
                project_id=project_id,
                proposal=proposal,
                approval_request_id=approval.id,
            )
            conversation_message_id = message.id
            self._conversation_repository.touch_updated_at(conversation_id)

        return MetaAgentSpecificationSubmission(
            specification=sanitized_specification,
            proposal=proposal,
            approval_request_id=approval.id,
            build_result=build_result,
            conversation_message_id=conversation_message_id,
        )

    def register_approved_proposal(
        self,
        *,
        project_id: UUID,
        approval_request_id: UUID,
        account: AuthenticatedAccount,
        actor_id: str,
    ) -> AgentProposalRegistrationResult:
        self._project_access.require_project(project_id, account)
        approval = self._approval.get_request(project_id, approval_request_id)
        if approval.target_action != "agent.create":
            raise MetaAgentUnsupportedRequestError(
                "Approval request is not for agent creation.",
            )
        if approval.status != ApprovalStatus.APPROVED:
            raise MetaAgentApprovalRequiredError(
                message="Human approval is required before an agent may be registered.",
                details={"approval_status": approval.status.value},
            )

        proposal = self._proposal_from_approval_metadata(approval.metadata)
        if proposal.status in {AgentProposalStatus.REJECTED, AgentProposalStatus.DISABLED}:
            raise MetaAgentUnsupportedRequestError(
                "Rejected or disabled proposals cannot be registered.",
            )

        registered = self._agent_registry_builder.create_agent(
            key=self._proposal_agent_key(proposal),
            name=proposal.name,
            description=proposal.purpose,
            project_id=project_id,
            instructions=proposal.prompt_instructions or proposal.description,
            capability_keys=[],
            created_by=actor_id,
            configuration={
                "meta_agent_proposal": {
                    "approval_request_id": str(approval_request_id),
                    "proposal_id": str(proposal.id) if proposal.id is not None else None,
                    "domain": proposal.domain,
                    "originating_user_request": proposal.originating_user_request,
                }
            },
        )

        return AgentProposalRegistrationResult(
            proposal_status=AgentProposalStatus.APPROVED,
            agent_id=registered.definition.id,
            agent_key=registered.definition.key,
            version=registered.version.version.version,
            agent_definition_status=registered.definition.status,
            agent_version_status=registered.version.version.status,
            message=(
                "Approved proposal registered as a draft agent. "
                "Publish approval is required before runtime activation."
            ),
            metadata={
                "approval_request_id": str(approval_request_id),
                "domain": proposal.domain,
            },
        )

    def request_build_after_approval(
        self,
        *,
        project_id: UUID,
        approval_request_id: UUID,
        account: AuthenticatedAccount,
        actor_id: str,
    ) -> AgentBuildResult:
        self._project_access.require_project(project_id, account)
        approval = self._approval.get_request(project_id, approval_request_id)
        if approval.target_action != "agent.create":
            raise MetaAgentUnsupportedRequestError(
                "Approval request is not for agent creation.",
            )
        if approval.status != ApprovalStatus.APPROVED:
            raise MetaAgentApprovalRequiredError(
                message="Human approval is required before agent build may proceed.",
                details={"approval_status": approval.status.value},
            )

        proposal = self._proposal_from_approval_metadata(approval.metadata)
        specification = proposal.to_specification()
        return self._agent_builder.submit_build(
            specification,
            approval_request_id=approval_request_id,
            project_id=project_id,
            requested_by=actor_id,
        )

    def _build_proposal(self, user_request: str) -> AgentProposal:
        name = self._derive_agent_name(user_request)
        return AgentProposal(
            id=uuid4(),
            status=AgentProposalStatus.DRAFT,
            name=name,
            purpose=f"Fulfill user request: {user_request[:240]}",
            description=(
                "Draft proposal for a new structural-engineering agent requested by the user. "
                "Implementation requires human approval and Agent Builder integration."
            ),
            domain=STRUCTURAL_ENGINEERING_DOMAIN,
            required_capabilities=self._derive_required_capabilities(user_request),
            expected_inputs=["user_request", "project_context"],
            expected_outputs=["structured_agent_response", "traceability_metadata"],
            prompt_instructions=(
                "You are a structural-engineering project assistant. Use only authorized project context, "
                "respect human approval gates, and never execute arbitrary code."
            ),
            tools_required=[],
            dependencies=["AgentRuntimeService", "HumanApprovalService"],
            authorization_requirements=[
                "Project-scoped access enforcement",
                "Human approval before activation",
            ],
            data_access_requirements=["project_context.read"],
            validation_requirements=[
                "No direct shell execution",
                "No bypass of Human Approval Gate",
                "No cross-project or cross-account data access",
                "No arbitrary executable code activation",
            ],
            approval_required=True,
            version="0.1.0-draft",
            originating_user_request=user_request,
        )

    def _derive_agent_name(self, user_request: str) -> str:
        cleaned = re.sub(r"\s+", " ", user_request.strip())[:80]
        if not cleaned:
            return "Custom Agent"
        return f"Custom Agent — {cleaned}"

    @staticmethod
    def _is_structural_engineering_scoped(user_request: str) -> bool:
        normalized = user_request.lower()
        return any(keyword in normalized for keyword in _STRUCTURAL_ENGINEERING_SCOPE_KEYWORDS)

    def _derive_required_capabilities(self, user_request: str) -> list[str]:
        normalized = user_request.lower()
        capabilities = ["request.planning", "project.context.read"]
        if any(term in normalized for term in ("report", "summary", "document", "pdf", "spec")):
            capabilities.append("document.interpret")
        capabilities.append("human.approval.enforced")
        return sorted(set(capabilities))

    def _sanitize_proposal(self, proposal: AgentProposal) -> AgentProposal:
        payload = proposal.model_copy(deep=True)
        payload.approval_required = True
        payload.domain = STRUCTURAL_ENGINEERING_DOMAIN
        for field_name in (
            "name",
            "purpose",
            "description",
            "originating_user_request",
            "prompt_instructions",
        ):
            value = getattr(payload, field_name)
            if isinstance(value, str):
                self._reject_forbidden_content(value)
        list_fields = (
            payload.required_capabilities,
            payload.expected_inputs,
            payload.expected_outputs,
            payload.tools_required,
            payload.dependencies,
            payload.authorization_requirements,
            payload.data_access_requirements,
            payload.validation_requirements,
        )
        for items in list_fields:
            for item in items:
                self._reject_forbidden_content(item)
        return payload

    def _sanitize_specification(self, specification: AgentSpecification) -> AgentSpecification:
        return self._sanitize_proposal(AgentProposal.from_specification(specification)).to_specification()

    def _proposal_from_approval_metadata(self, metadata: dict) -> AgentProposal:
        raw_proposal = metadata.get("agent_proposal")
        if isinstance(raw_proposal, dict):
            return self._sanitize_proposal(AgentProposal.model_validate(raw_proposal))
        raw_spec = metadata.get("agent_specification")
        if isinstance(raw_spec, dict):
            return self._sanitize_proposal(
                AgentProposal.from_specification(AgentSpecification.model_validate(raw_spec))
            )
        raise MetaAgentUnsupportedRequestError("Approved agent proposal payload is missing.")

    def _record_proposal_provenance(
        self,
        *,
        conversation_id: UUID,
        account: AuthenticatedAccount,
        project_id: UUID,
        proposal: AgentProposal,
        approval_request_id: UUID,
    ):
        conversation = self._conversation_repository.get_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        if conversation.account_id != account.account_id:
            raise ConversationForbiddenError("You do not have access to this conversation.")
        if conversation.project_id is not None and conversation.project_id != project_id:
            raise ConversationForbiddenError("Conversation project does not match the submission project.")

        return self._conversation_repository.create_message(
            conversation_id=conversation_id,
            role=MessageRole.SYSTEM,
            content="A new agent proposal was submitted for human approval.",
            metadata={
                "meta_agent_proposal": {
                    "approval_request_id": str(approval_request_id),
                    "proposal_id": str(proposal.id) if proposal.id is not None else None,
                    "proposal_name": proposal.name,
                    "proposal_status": proposal.status.value,
                    "domain": proposal.domain,
                    "originating_user_request": proposal.originating_user_request,
                }
            },
        )

    @staticmethod
    def _proposal_agent_key(proposal: AgentProposal) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", proposal.name.lower()).strip("-")[:40] or "custom-agent"
        return f"meta-{slug}-{uuid4().hex[:8]}"

    @staticmethod
    def _reject_forbidden_content(value: str) -> None:
        for pattern in _FORBIDDEN_SPEC_PATTERNS:
            if pattern.search(value):
                raise MetaAgentUnsupportedRequestError(
                    "Agent proposal contains disallowed executable instructions.",
                )
