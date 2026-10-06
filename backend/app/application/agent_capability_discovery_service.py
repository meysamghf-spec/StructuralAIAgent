"""Deterministic capability discovery for Meta-Agent routing."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.agent_access_service import AgentAccessService
from app.application.agent_capability_catalog import get_agent_capability_profile
from app.application.agent_intent_routing import (
    requests_new_agent_creation,
    score_agent_intents,
)
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.meta_agent import AgentCapabilityMatch
from app.domain.models.user import AuthenticatedAccount

_MATCH_CONFIDENCE_BASE = 0.45
_MATCH_CONFIDENCE_PER_KEYWORD = 0.15
_MATCH_CONFIDENCE_CAP = 0.95
_ROUTE_THRESHOLD = 0.45


@dataclass(frozen=True)
class CapabilityDiscoveryResult:
    matches: list[AgentCapabilityMatch]
    requires_new_agent: bool
    reason: str
    best_match: AgentCapabilityMatch | None = None


class AgentCapabilityDiscoveryService:
    def __init__(self, *, agent_access: AgentAccessService) -> None:
        self._agent_access = agent_access

    def discover(
        self,
        user_request: str,
        account: AuthenticatedAccount,
        *,
        project_id: UUID | None = None,
    ) -> CapabilityDiscoveryResult:
        trimmed = user_request.strip()
        if not trimmed:
            return CapabilityDiscoveryResult(
                matches=[],
                requires_new_agent=False,
                reason="Request is empty.",
                best_match=None,
            )

        if requests_new_agent_creation(trimmed):
            return CapabilityDiscoveryResult(
                matches=[],
                requires_new_agent=True,
                reason="Request explicitly asks to create a new agent.",
                best_match=None,
            )

        accessible_types = self._accessible_agent_types(account, project_id=project_id)
        matches = self._score_matches(trimmed, accessible_types)
        best_match = matches[0] if matches else None

        if best_match is not None and best_match.confidence >= _ROUTE_THRESHOLD:
            return CapabilityDiscoveryResult(
                matches=matches,
                requires_new_agent=False,
                reason=(
                    f"Matched existing capability '{best_match.agent_name}' "
                    f"with confidence {best_match.confidence:.2f}."
                ),
                best_match=best_match,
            )

        if best_match is not None:
            return CapabilityDiscoveryResult(
                matches=matches,
                requires_new_agent=False,
                reason=(
                    f"Weak match to '{best_match.agent_name}' "
                    f"(confidence {best_match.confidence:.2f}); routing to best existing agent."
                ),
                best_match=best_match,
            )

        return CapabilityDiscoveryResult(
            matches=[],
            requires_new_agent=True,
            reason="No existing platform agent capability matches this request.",
            best_match=None,
        )

    def _accessible_agent_types(
        self,
        account: AuthenticatedAccount,
        *,
        project_id: UUID | None,
    ) -> set[EngineeringAgentType]:
        definitions = self._agent_access.list_accessible_agents(account, project_id=project_id)
        types = {
            definition.agent_type
            for definition in definitions
            if definition.agent_type is not None
            and definition.agent_type != EngineeringAgentType.PROMPT_GENERATION_AGENT
        }
        if types:
            return types
        return {
            agent_type
            for agent_type in EngineeringAgentType
            if agent_type != EngineeringAgentType.PROMPT_GENERATION_AGENT
        }

    def _score_matches(
        self,
        user_request: str,
        accessible_types: set[EngineeringAgentType],
    ) -> list[AgentCapabilityMatch]:
        matches: list[AgentCapabilityMatch] = []
        for intent in score_agent_intents(user_request):
            if intent.agent_type not in accessible_types:
                continue
            profile = get_agent_capability_profile(intent.agent_type)
            confidence = min(
                _MATCH_CONFIDENCE_CAP,
                _MATCH_CONFIDENCE_BASE + _MATCH_CONFIDENCE_PER_KEYWORD * intent.score,
            )
            matches.append(
                AgentCapabilityMatch(
                    agent_type=intent.agent_type,
                    agent_name=profile.name,
                    confidence=confidence,
                    reason=intent.intent_label,
                    matched_capabilities=list(profile.capabilities),
                    matched_keywords=list(intent.matched_keywords),
                )
            )
        matches.sort(key=lambda item: item.confidence, reverse=True)
        return matches
