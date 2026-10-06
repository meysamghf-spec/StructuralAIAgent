"""Read-model for the generated building so the UI does not invent a second geometry."""

from __future__ import annotations

from typing import Any

from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_architecture import Polygon2D
from app.domain.models.pem_structural import MemberType


def serialize_building_view(pem: ProjectEngineeringModel) -> dict[str, Any]:
    building = pem.building_model
    structural = pem.structural_model
    site = None
    if building.site is not None:
        site = {
            "id": building.site.id,
            "name": building.site.name,
            "frontage_m": building.site.frontage_m,
            "depth_m": building.site.depth_m,
            "orientation_deg": building.site.orientation_deg,
            "setbacks_m": {
                "front": building.site.setback_front_m,
                "rear": building.site.setback_rear_m,
                "left": building.site.setback_left_m,
                "right": building.site.setback_right_m,
            },
            "plot_area_m2": building.site.plot_area_m2,
            "boundary": _polygon(building.site.boundary),
            "buildable": _polygon(building.site.buildable_boundary),
        }

    floors = []
    for plan in building.floor_plans:
        floors.append(
            {
                "id": plan.id,
                "name": plan.name,
                "level_id": plan.level_id,
                "floor_type": plan.floor_type.value,
                "elevation_m": plan.elevation_m,
                "storey_height_m": plan.storey_height_m,
                "gross_area_m2": plan.gross_area_m2,
                "boundary": _polygon(plan.boundary),
                "spaces": [
                    {
                        "id": space.id,
                        "name": space.name,
                        "usage": space.usage.value,
                        "area_m2": space.area_m2,
                        "boundary": _polygon(space.boundary),
                    }
                    for space in plan.spaces
                ],
                "walls": [
                    {
                        "id": wall.id,
                        "start": {"x": wall.start.x, "y": wall.start.y},
                        "end": {"x": wall.end.x, "y": wall.end.y},
                        "thickness_m": wall.thickness_m,
                    }
                    for wall in plan.walls
                ],
                "doors": [
                    {
                        "id": door.id,
                        "center": {"x": door.center.x, "y": door.center.y},
                        "width_m": door.width_m,
                    }
                    for door in plan.doors
                ],
                "windows": [
                    {
                        "id": window.id,
                        "center": {"x": window.center.x, "y": window.center.y},
                        "width_m": window.width_m,
                    }
                    for window in plan.windows
                ],
                "parking_spaces": [
                    {
                        "id": slot.id,
                        "label": slot.label,
                        "area_m2": slot.area_m2,
                        "boundary": _polygon(slot.boundary),
                    }
                    for slot in plan.parking_spaces
                ],
                "apartments": [
                    {
                        "id": apartment.id,
                        "name": apartment.name,
                        "bedroom_count": apartment.bedroom_count,
                        "space_ids": apartment.space_ids,
                    }
                    for apartment in plan.apartments
                ],
            }
        )

    points = {point.id: point for point in structural.geometry.points}
    columns = []
    beams = []
    slabs = []
    for member in structural.members.members:
        if member.member_type is MemberType.COLUMN:
            point = points.get(member.start_point_id or "")
            columns.append(
                {
                    "id": member.id,
                    "name": member.name,
                    "section_id": member.section_id,
                    "x": point.x if point else None,
                    "y": point.y if point else None,
                    "z": point.z if point else None,
                }
            )
        elif member.member_type is MemberType.BEAM:
            start = points.get(member.start_point_id or "")
            end = points.get(member.end_point_id or "")
            beams.append(
                {
                    "id": member.id,
                    "name": member.name,
                    "section_id": member.section_id,
                    "start": {"x": start.x, "y": start.y, "z": start.z} if start else None,
                    "end": {"x": end.x, "y": end.y, "z": end.z} if end else None,
                }
            )
        elif member.member_type is MemberType.SLAB:
            area = next(
                (item for item in structural.geometry.areas if item.id == member.area_id),
                None,
            )
            slabs.append(
                {
                    "id": member.id,
                    "name": member.name,
                    "section_id": member.section_id,
                    "boundary": _area_polygon(structural, area.id) if area else [],
                }
            )

    grid = structural.geometry.grids[0].metadata if structural.geometry.grids else {}
    return {
        "project_id": str(pem.project_id),
        "project_name": pem.metadata.name,
        "site": site,
        "floors": floors,
        "stairs": [
            {
                "id": stair.id,
                "name": stair.name,
                "boundary": _polygon(stair.boundary),
                "served_level_ids": stair.served_level_ids,
            }
            for stair in building.stairs
        ],
        "cores": [
            {
                "id": core.id,
                "name": core.name,
                "boundary": _polygon(core.boundary),
            }
            for core in building.cores
        ],
        "structural_system": building.structural_system.value,
        "grid": {
            "x_ordinates": list(grid.get("x_ordinates") or []),
            "y_ordinates": list(grid.get("y_ordinates") or []),
            "x_labels": list(grid.get("x_labels") or []),
            "y_labels": list(grid.get("y_labels") or []),
        },
        "columns": columns,
        "beams": beams,
        "slabs": slabs,
        "load_cases": [
            {
                "id": case.id,
                "name": case.name,
                "category": case.category.value,
                "fidelity": (case.metadata or {}).get("fidelity"),
            }
            for case in structural.load_cases
        ],
        "load_combinations": [
            {
                "id": combo.id,
                "name": combo.name,
                "code_source": combo.code_source,
                "fidelity": (combo.metadata or {}).get("fidelity"),
            }
            for combo in structural.load_combinations
        ],
        "design_checks": [check.model_dump(mode="json") for check in structural.design_checks],
        "reinforcement": [item.model_dump(mode="json") for item in structural.reinforcement],
        "qa_findings": pem.validation_results,
        "assumptions": pem.assumptions,
        "analysis": structural.analysis_model.configuration,
        "story_drifts": [item.model_dump(mode="json") for item in structural.story_drifts],
        "story_forces": [item.model_dump(mode="json") for item in structural.story_forces],
        "footings": [item.model_dump(mode="json") for item in structural.footings],
        "input_provenance": [item.model_dump(mode="json") for item in structural.input_provenance],
        "engineering_report": pem.engineering_report,
        "lifecycle_status": pem.lifecycle_status,
        "code_compliance": pem.code_compliance,
        "disclaimer": (
            "Preliminary automated engineering model — requires review and approval "
            "by a qualified engineer."
        ),
        "counts": {
            "floors": building.floor_count,
            "spaces": len(building.all_spaces()),
            "parking": len(building.all_parking_spaces()),
            "stairs": len(building.stairs),
            "columns": len(columns),
            "beams": len(beams),
            "slabs": len(slabs),
            "load_cases": len(structural.load_cases),
            "design_checks": len(structural.design_checks),
            "footings": len(structural.footings),
        },
    }


def _polygon(polygon: Polygon2D) -> list[dict[str, float]]:
    return [{"x": point.x, "y": point.y} for point in polygon.points]


def _area_polygon(structural, area_id: str) -> list[dict[str, float]]:
    area = next((item for item in structural.geometry.areas if item.id == area_id), None)
    if area is None:
        return []
    points = {point.id: point for point in structural.geometry.points}
    ring = []
    for point_id in area.boundary_point_ids:
        point = points.get(point_id)
        if point is not None:
            ring.append({"x": point.x, "y": point.y})
    return ring
