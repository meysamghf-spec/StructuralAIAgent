"""Deterministic scored keyword routing shared by prompt generation and Meta-Agent discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.models.agent import EngineeringAgentType

ATTACHMENT_CONTEXT_MARKERS: tuple[str, ...] = (
    "Attached files (engineering context):",
    "\nAttached files:",
)

USER_REQUEST_SCORE_WEIGHT = 1.0
ATTACHMENT_SCORE_WEIGHT = 0.2

_LATIN_KEYWORD_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}

AGENT_INTENT_ROUTING: list[tuple[tuple[str, ...], EngineeringAgentType, str]] = [
    (
        (
            "structural engineering agent",
            "structural workflow",
            "run the structural workflow",
        ),
        EngineeringAgentType.STRUCTURAL_ENGINEERING_AGENT,
        "Run the structural engineering workflow on the current project",
    ),
    (
        (
            "design this building",
            "design the building",
            "building brief",
            "building layout",
            "residential floors",
            "parking spaces",
            "floor plan",
            "این ساختمان",
            "ساختمان را طراحی",
            "طراحی کن",
            "پیلوت",
            "طبقه مسکونی",
            "پارکینگ",
            "زمین",
        ),
        EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
        "Generate architectural and structural building layout from a brief",
    ),
    (
        ("structural model", "geometry", "model", "مدل", "هندسی"),
        EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
        "Set up or revise the structural engineering model",
    ),
    (
        ("seismic analysis", "seismic design", "seismic", "earthquake", "spectral", "زلزله", "لرزه"),
        EngineeringAgentType.SEISMIC_AGENT,
        "Evaluate seismic design parameters and lateral system assumptions",
    ),
    (
        ("dead load", "live load", "loading", "loads", "load", "بار"),
        EngineeringAgentType.LOAD_ASSESSMENT_AGENT,
        "Review and organize project loading assumptions",
    ),
    (
        ("analyze", "analysis", "modal", "drift", "simply supported", "uniform load", "udl", "تحلیل"),
        EngineeringAgentType.ANALYSIS_AGENT,
        "Run or review structural analysis workflows",
    ),
    (
        (
            "reinforced concrete",
            "reinforcement",
            "rc beam",
            "rc column",
            "concrete beam",
            "design this beam",
            "design the beam",
            "aci 318",
            "aci",
            "concrete",
            "rebar",
            "slab",
            "بتن",
        ),
        EngineeringAgentType.CONCRETE_DESIGN_AGENT,
        "Support concrete member and slab design checks",
    ),
    (
        (
            "steel beam",
            "steel member",
            "aisc 360",
            "aisc",
            "w-shape",
            "wide flange",
            "plastic modulus",
            "steel",
            "beam",
            "column",
            "connection",
            "فولاد",
        ),
        EngineeringAgentType.STEEL_DESIGN_AGENT,
        "Support steel member sizing and connection review",
    ),
    (
        ("validate", "validation", "code check", "بررسی", "کنترل"),
        EngineeringAgentType.VALIDATION_AGENT,
        "Validate configuration, assumptions, and code compliance",
    ),
    (
        ("cad", "drawings", "drawing", "autocad", "dxf", "dwg", "نقشه", "اجرا"),
        EngineeringAgentType.CAD_AGENT,
        "Prepare or coordinate engineering drawings and CAD deliverables",
    ),
    (
        ("report", "reports", "summary", "deliverable", "گزارش"),
        EngineeringAgentType.REPORTING_AGENT,
        "Prepare engineering summaries and deliverable reports",
    ),
    (
        ("document", "specification", "spec", "interpret", "pdf", "سند", "مشخصات"),
        EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT,
        "Interpret uploaded documents and specifications",
    ),
    (
        ("optimize", "optimization", "بهینه"),
        EngineeringAgentType.OPTIMIZATION_AGENT,
        "Plan and run structural optimization workflows",
    ),
]

CREATE_AGENT_KEYWORDS: tuple[str, ...] = (
    "create agent",
    "create an agent",
    "build agent",
    "build an agent",
    "new agent",
    "new assistant",
    "custom agent",
    "custom assistant",
    "meta-agent",
    "meta agent",
)

UNSUPPORTED_REQUEST_MAX_LENGTH = 4096

_DEFAULT_FALLBACK_LABEL = "Review project readiness and identify next engineering steps"


@dataclass(frozen=True)
class AgentIntentScore:
    agent_type: EngineeringAgentType
    intent_label: str
    score: float
    matched_keywords: tuple[str, ...]


def requests_new_agent_creation(user_request: str) -> bool:
    normalized = user_request.strip().lower()
    return any(keyword in normalized for keyword in CREATE_AGENT_KEYWORDS)


def split_user_request_and_attachment_context(text: str) -> tuple[str, str]:
    source = text or ""
    for marker in ATTACHMENT_CONTEXT_MARKERS:
        index = source.find(marker)
        if index >= 0:
            return source[:index].strip(), source[index + len(marker) :].strip()
    return source.strip(), ""


def keyword_matches(keyword: str, normalized_text: str) -> bool:
    if not keyword or not normalized_text:
        return False
    if any(ord(character) > 127 for character in keyword):
        return keyword in normalized_text
    if " " in keyword:
        return keyword in normalized_text
    pattern = _LATIN_KEYWORD_PATTERN_CACHE.get(keyword)
    if pattern is None:
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])")
        _LATIN_KEYWORD_PATTERN_CACHE[keyword] = pattern
    return pattern.search(normalized_text) is not None


def keyword_weight(keyword: str) -> float:
    tokens = keyword.split()
    if len(tokens) >= 2:
        return 3.0 + 0.5 * (len(tokens) - 2)
    if len(keyword) >= 8:
        return 2.5
    if len(keyword) >= 5:
        return 2.0
    return 1.0


def score_agent_intents(text: str) -> list[AgentIntentScore]:
    normalized = (text or "").lower()
    matches: list[AgentIntentScore] = []
    for keywords, agent_type, intent_label in AGENT_INTENT_ROUTING:
        hit_keywords = tuple(keyword for keyword in keywords if keyword_matches(keyword, normalized))
        if not hit_keywords:
            continue
        score = sum(keyword_weight(keyword) for keyword in hit_keywords)
        matches.append(
            AgentIntentScore(
                agent_type=agent_type,
                intent_label=intent_label,
                score=score,
                matched_keywords=hit_keywords,
            )
        )
    matches.sort(key=lambda item: (-item.score, _route_index(item.agent_type)))
    return matches


def resolve_agent_intent(user_request: str) -> AgentIntentScore:
    user_part, attachment_part = split_user_request_and_attachment_context(user_request)
    combined: dict[EngineeringAgentType, AgentIntentScore] = {}

    _merge_intent_scores(combined, score_agent_intents(user_part), USER_REQUEST_SCORE_WEIGHT)
    if attachment_part:
        _merge_intent_scores(combined, score_agent_intents(attachment_part), ATTACHMENT_SCORE_WEIGHT)

    if not combined:
        return AgentIntentScore(
            agent_type=EngineeringAgentType.VALIDATION_AGENT,
            intent_label=_DEFAULT_FALLBACK_LABEL,
            score=0.0,
            matched_keywords=(),
        )

    ranked = sorted(
        combined.values(),
        key=lambda item: (-item.score, _route_index(item.agent_type)),
    )
    return ranked[0]


def resolve_primary_agent_type(user_request: str) -> tuple[EngineeringAgentType, str]:
    intent = resolve_agent_intent(user_request)
    return intent.agent_type, intent.intent_label


def _merge_intent_scores(
    combined: dict[EngineeringAgentType, AgentIntentScore],
    scores: list[AgentIntentScore],
    weight: float,
) -> None:
    for item in scores:
        weighted_score = item.score * weight
        existing = combined.get(item.agent_type)
        if existing is None:
            combined[item.agent_type] = AgentIntentScore(
                agent_type=item.agent_type,
                intent_label=item.intent_label,
                score=weighted_score,
                matched_keywords=item.matched_keywords,
            )
            continue
        merged_keywords = tuple(dict.fromkeys((*existing.matched_keywords, *item.matched_keywords)))
        combined[item.agent_type] = AgentIntentScore(
            agent_type=item.agent_type,
            intent_label=existing.intent_label,
            score=existing.score + weighted_score,
            matched_keywords=merged_keywords,
        )


def _route_index(agent_type: EngineeringAgentType) -> int:
    for index, (_, routed_type, _) in enumerate(AGENT_INTENT_ROUTING):
        if routed_type == agent_type:
            return index
    return len(AGENT_INTENT_ROUTING)
