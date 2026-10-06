"""PDF drawing sheets generated from the same PEM geometry as the DXF views."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_architecture import FloorType
from app.infrastructure.config import get_settings
from app.infrastructure.reporting.pdf_sheet_renderer import write_pdf_sheet


class SheetGenerationService:
    def generate_project_sheets(
        self,
        project_id: UUID,
        pem: ProjectEngineeringModel,
        *,
        pem_version: int,
    ) -> list[str]:
        output_dir = Path(get_settings().resolved_file_storage_root) / "sheets" / str(project_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        sheets = [
            ("A-001", "Site plan", self._site_geometry(pem)),
            ("A-101", "Ground / pilot plan", self._floor_geometry(pem, FloorType.PILOTI)),
            ("A-102", "Typical residential plan", self._floor_geometry(pem, FloorType.RESIDENTIAL)),
            ("S-001", "General notes / grid", self._grid_geometry(pem)),
            ("S-101", "Foundation / column layout", self._grid_geometry(pem)),
            ("S-102", "Column layout", self._grid_geometry(pem)),
            ("S-103", "Beam layout", self._grid_geometry(pem)),
            ("S-104", "Slab layout", self._grid_geometry(pem)),
        ]
        paths: list[str] = []
        for number, title, (lines, labels, width, height) in sheets:
            if not lines:
                continue
            path = output_dir / f"{number}_{pem_version}.pdf"
            write_pdf_sheet(
                path,
                title=title,
                project_name=pem.metadata.name,
                sheet_number=number,
                scale="1:100",
                notes=[
                    "Preliminary automated engineering model — requires review and approval by a qualified engineer.",
                    f"PEM version {pem_version}",
                    "Confirm dimensions on site. Not a construction issue set until approved.",
                ],
                lines=lines,
                labels=labels,
                model_width=width,
                model_height=height,
            )
            paths.append(str(path))
        return paths

    @staticmethod
    def _site_geometry(pem: ProjectEngineeringModel):
        site = pem.building_model.site
        if site is None:
            return [], [], 1.0, 1.0
        lines = _ring(site.boundary.points)
        buildable = site.buildable_boundary
        if buildable.points:
            lines.extend(_ring(buildable.points))
        labels = [(site.boundary.centroid.x, site.boundary.centroid.y, "PLOT")]
        return lines, labels, max(site.frontage_m, 1.0), max(site.depth_m, 1.0)

    @staticmethod
    def _floor_geometry(pem: ProjectEngineeringModel, floor_type: FloorType):
        plan = next((item for item in pem.building_model.floor_plans if item.floor_type is floor_type), None)
        if plan is None:
            return [], [], 1.0, 1.0
        lines = _ring(plan.boundary.points)
        labels = []
        for space in plan.spaces:
            lines.extend(_ring(space.boundary.points))
            centre = space.boundary.centroid
            labels.append((centre.x, centre.y, space.name))
        for slot in plan.parking_spaces:
            lines.extend(_ring(slot.boundary.points))
            centre = slot.boundary.centroid
            labels.append((centre.x, centre.y, slot.label))
        bounds = plan.boundary.bounds
        return lines, labels, max(bounds[2] - bounds[0], 1.0), max(bounds[3] - bounds[1], 1.0)

    @staticmethod
    def _grid_geometry(pem: ProjectEngineeringModel):
        grid = pem.structural_model.geometry.grids[0].metadata if pem.structural_model.geometry.grids else {}
        x_vals = [float(v) for v in grid.get("x_ordinates") or []]
        y_vals = [float(v) for v in grid.get("y_ordinates") or []]
        if not x_vals or not y_vals:
            return [], [], 1.0, 1.0
        lines = []
        labels = []
        x_labels = list(grid.get("x_labels") or [])
        y_labels = list(grid.get("y_labels") or [])
        for x_value, label in zip(x_vals, x_labels or x_vals):
            lines.append((x_value, y_vals[0], x_value, y_vals[-1]))
            labels.append((x_value, y_vals[0], str(label)))
        for y_value, label in zip(y_vals, y_labels or y_vals):
            lines.append((x_vals[0], y_value, x_vals[-1], y_value))
            labels.append((x_vals[0], y_value, str(label)))
        return lines, labels, max(x_vals[-1] - x_vals[0], 1.0), max(y_vals[-1] - y_vals[0], 1.0)


def _ring(points) -> list[tuple[float, float, float, float]]:
    lines: list[tuple[float, float, float, float]] = []
    for index in range(len(points)):
        start = points[index]
        end = points[(index + 1) % len(points)]
        lines.append((start.x, start.y, end.x, end.y))
    return lines
