"""
Builds the complete :class:`DrawingSet` for a PEM snapshot.

The sheet list is declared once in :data:`SHEET_SPECS` so the drawing index
printed on S-001 and the sheets actually generated can never drift apart.

Generation is deterministic: given the same PEM and the same ``generated_at``,
the geometry, the primitive IDs and therefore every sheet signature come out
identical. Only sheets whose phase is implemented appear here; schedules
(S-201..S-203), structural sections (S-301) and reinforcement details (S-401)
are later milestones and are deliberately absent rather than stubbed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.application.drawing.architectural_sheets import (
    build_architectural_sections,
    build_elevations,
    build_ground_plan,
    build_site_plan,
    build_typical_residential_plan,
)
from app.application.drawing.pem_solids import PemDrawingContext
from app.application.drawing.sheet_builder import SheetBuildContext
from app.application.drawing.structural_sheets import (
    build_beam_layout,
    build_column_layout,
    build_foundation_plan,
    build_slab_layout,
    build_structural_notes,
)
from app.domain.models.drawing import Discipline, DrawingSet, DrawingSheet
from app.domain.models.pem import ProjectEngineeringModel


@dataclass(frozen=True)
class SheetSpec:
    number: str
    title: str
    discipline: Discipline
    builder: Callable[[SheetBuildContext], DrawingSheet]


SHEET_SPECS: tuple[SheetSpec, ...] = (
    SheetSpec("A-001", "Site / general plan", Discipline.ARCHITECTURAL, build_site_plan),
    SheetSpec("A-101", "Ground / parking plan", Discipline.ARCHITECTURAL, build_ground_plan),
    SheetSpec(
        "A-102",
        "Typical residential plan",
        Discipline.ARCHITECTURAL,
        build_typical_residential_plan,
    ),
    SheetSpec("A-201", "Elevations", Discipline.ARCHITECTURAL, build_elevations),
    SheetSpec("A-301", "Sections A-A and B-B", Discipline.ARCHITECTURAL, build_architectural_sections),
    SheetSpec("S-001", "Structural general notes", Discipline.STRUCTURAL, build_structural_notes),
    SheetSpec("S-101", "Foundation plan", Discipline.STRUCTURAL, build_foundation_plan),
    SheetSpec("S-102", "Column layout", Discipline.STRUCTURAL, build_column_layout),
    SheetSpec("S-103", "Beam layout", Discipline.STRUCTURAL, build_beam_layout),
    SheetSpec(
        "S-104",
        "Slab layout and diaphragm assignment",
        Discipline.STRUCTURAL,
        build_slab_layout,
    ),
)

STRUCTURAL_SHEET_NUMBERS: tuple[str, ...] = tuple(
    spec.number for spec in SHEET_SPECS if spec.discipline is Discipline.STRUCTURAL
)
ARCHITECTURAL_SHEET_NUMBERS: tuple[str, ...] = tuple(
    spec.number for spec in SHEET_SPECS if spec.discipline is Discipline.ARCHITECTURAL
)


class DrawingSetService:
    """Turns a persisted PEM into a traceable drawing set."""

    def generate(
        self,
        pem: ProjectEngineeringModel,
        *,
        project_id: UUID | None = None,
        pem_version: int | None = None,
        snapshot_id: UUID | str | None = None,
        revision: str = "0",
        generated_at: datetime | None = None,
        only: tuple[str, ...] | None = None,
    ) -> DrawingSet:
        pem_context = PemDrawingContext(pem)
        stamp = generated_at or datetime.now(UTC)
        specs = [spec for spec in SHEET_SPECS if only is None or spec.number in only]

        context = SheetBuildContext(
            pem=pem_context,
            project_name=pem.metadata.name,
            source_model_id=str(pem.id),
            generated_at=stamp,
            source_snapshot_id=str(snapshot_id) if snapshot_id is not None else None,
            pem_version=pem_version,
            revision=revision,
            units=pem.building_model.length_unit or "m",
            drawing_index=[(spec.number, spec.title) for spec in specs],
        )

        sheets = [spec.builder(context) for spec in specs]
        resolved_project_id = project_id or pem.project_id
        return DrawingSet(
            id=f"DS-{resolved_project_id}-{pem_version if pem_version is not None else 0}-r{revision}",
            project_id=resolved_project_id,
            project_name=pem.metadata.name,
            source_model_id=str(pem.id),
            source_snapshot_id=str(snapshot_id) if snapshot_id is not None else None,
            pem_version=pem_version,
            revision=revision,
            generated_at=stamp,
            units=context.units,
            sheets=sheets,
            disclaimers=context.standard_notes() + context.limitations,
            metadata={
                "lifecycle_status": pem.lifecycle_status,
                "sheet_count": len(sheets),
                "architectural_sheets": [
                    sheet.sheet_number
                    for sheet in sheets
                    if sheet.discipline is Discipline.ARCHITECTURAL
                ],
                "structural_sheets": [
                    sheet.sheet_number
                    for sheet in sheets
                    if sheet.discipline is Discipline.STRUCTURAL
                ],
                "level_ids": [level.id for level in pem_context.levels_sorted],
                "pending_milestones": [
                    "S-201 beam schedule",
                    "S-202 column schedule",
                    "S-203 slab / reinforcement schedule",
                    "S-301 structural sections",
                    "S-401 reinforcement details",
                ],
            },
        )
