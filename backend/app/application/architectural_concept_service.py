"""Derive structured architectural concepts from natural-language requests."""

from __future__ import annotations

import re
from typing import Any

from app.domain.models.architectural_concept import ArchitecturalConcept, ArchitecturalSpace
from app.domain.models.engineering_task import AssumptionSource, EngineeringAssumption


class ArchitecturalConceptService:
    def derive_concept(self, user_request: str) -> ArchitecturalConcept:
        normalized = user_request.strip()
        lower = normalized.lower()
        concept = ArchitecturalConcept(
            story_count=self._parse_story_count(lower),
            plan_length_m=self._parse_plan_dimension(lower, index=0),
            plan_width_m=self._parse_plan_dimension(lower, index=1),
            circulation=self._parse_circulation(lower),
            functional_zones=self._parse_zones(lower),
        )
        if concept.plan_length_m and concept.plan_width_m:
            concept.total_plan_area_m2 = round(concept.plan_length_m * concept.plan_width_m, 2)
        concept.spaces = self._parse_spaces(lower)
        concept.assumptions = self._concept_assumptions(concept)
        concept.limitations = [
            "Architectural concept is a structured zoning/layout summary, not a full architectural design package.",
            "Detailed architectural code compliance and MEP coordination are not included in this stage.",
        ]
        if not concept.spaces and not concept.story_count:
            concept.limitations.append(
                "Insufficient architectural detail was parsed from the request; provide room counts and plan dimensions."
            )
        return concept

    def concept_to_assumptions(self, concept: ArchitecturalConcept) -> list[EngineeringAssumption]:
        assumptions: list[EngineeringAssumption] = []
        if concept.story_count is not None:
            assumptions.append(
                EngineeringAssumption(
                    field_name="Number of stories",
                    value=str(concept.story_count),
                    source=AssumptionSource.USER_PROVIDED,
                )
            )
        if concept.plan_length_m and concept.plan_width_m:
            assumptions.append(
                EngineeringAssumption(
                    field_name="Plan dimensions",
                    value=f"{concept.plan_length_m} m x {concept.plan_width_m} m",
                    source=AssumptionSource.USER_PROVIDED,
                )
            )
        for space in concept.spaces:
            assumptions.append(
                EngineeringAssumption(
                    field_name=space.name,
                    value=str(space.count),
                    source=AssumptionSource.USER_PROVIDED,
                    notes=space.space_type,
                )
            )
        return assumptions

    def render_zoning_dxf(self, concept: ArchitecturalConcept) -> dict[str, Any] | None:
        if not concept.plan_length_m or not concept.plan_width_m:
            return None
        from app.infrastructure.cad.dxf_renderer import render_architectural_zoning_dxf

        result = render_architectural_zoning_dxf(concept)
        return {
            "content": result.content,
            "entity_count": result.entity_count,
            "layer_summary": result.layer_summary,
            "metadata": result.metadata,
            "filename": "architectural_zoning_plan.dxf",
        }

    @staticmethod
    def _parse_story_count(text: str) -> int | None:
        match = re.search(r"(\d+)\s*[- ]?stor", text)
        return int(match.group(1)) if match else None

    @staticmethod
    def _parse_plan_dimension(text: str, *, index: int) -> float | None:
        match = re.search(
            r"(\d+(?:\.\d+)?)\s*m\s*[x×]\s*(\d+(?:\.\d+)?)\s*m",
            text,
        )
        if not match:
            return None
        return float(match.group(index + 1))

    @staticmethod
    def _parse_spaces(text: str) -> list[ArchitecturalSpace]:
        spaces: list[ArchitecturalSpace] = []
        patterns = [
            (r"(\d+)\s*master\s+bed(?:room)?s?", "Master bedroom", "bedroom"),
            (r"(\d+)\s*bed(?:room)?s?", "Bedroom", "bedroom"),
            (r"(\d+)\s*bath(?:room)?s?", "Bathroom", "bathroom"),
            (r"(\d+)\s*kitchens?", "Kitchen", "kitchen"),
            (r"(\d+)\s*living\s+rooms?", "Living room", "living"),
        ]
        seen: set[str] = set()
        for pattern, label, space_type in patterns:
            for match in re.finditer(pattern, text):
                key = f"{label}:{match.group(1)}"
                if key in seen:
                    continue
                seen.add(key)
                spaces.append(
                    ArchitecturalSpace(
                        name=label,
                        space_type=space_type,
                        count=int(match.group(1)),
                    )
                )
        if "master bedroom" in text and not any(item.name == "Master bedroom" for item in spaces):
            spaces.append(ArchitecturalSpace(name="Master bedroom", space_type="bedroom", count=1))
        if ("bathroom" in text or "حمام" in text) and not any(item.space_type == "bathroom" for item in spaces):
            spaces.append(ArchitecturalSpace(name="Bathroom", space_type="bathroom", count=1))
        return spaces

    @staticmethod
    def _parse_circulation(text: str) -> list[str]:
        items: list[str] = []
        if any(term in text for term in ("stair", "stairs", "راه پله")):
            items.append("Stairs required")
        if "elevator" in text or "lift" in text:
            items.append("Elevator required")
        if "entrance" in text or "lobby" in text:
            items.append("Primary entrance/lobby")
        if not items:
            items.append("Core circulation to be confirmed")
        return items

    @staticmethod
    def _parse_zones(text: str) -> list[str]:
        zones: list[str] = []
        if any(term in text for term in ("bedroom", "master", "اتاق")):
            zones.append("Private sleeping zone")
        if any(term in text for term in ("bathroom", "حمام", "سرویس")):
            zones.append("Sanitary zone")
        if any(term in text for term in ("kitchen", "آشپز")):
            zones.append("Service zone")
        if "two-way" in text or "two way" in text or "قاب" in text:
            zones.append("Two-way reinforced concrete frame structural zone")
        return zones

    @staticmethod
    def _concept_assumptions(concept: ArchitecturalConcept) -> list[str]:
        notes: list[str] = []
        if concept.story_count:
            notes.append(f"{concept.story_count}-story building assumed from request text.")
        if concept.total_plan_area_m2:
            notes.append(f"Approximate plan area {concept.total_plan_area_m2} m² from parsed dimensions.")
        if concept.spaces:
            notes.append("Room counts parsed from request text; exact layout coordinates are not inferred.")
        return notes
