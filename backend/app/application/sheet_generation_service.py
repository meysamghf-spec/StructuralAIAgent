"""
Writes the PEM-driven drawing set to disk.

Replaces the previous placeholder, which plotted the same structural grid onto
S-101 to S-104 under four different titles. Sheets now come from
:class:`DrawingSetService`, so each one is a projection of the PEM elements it is
about.

Three artefacts are produced per PEM version:

* one PDF per sheet, named ``<sheet>_<version>.pdf`` — the layout the existing
  ``/building/sheets/{name}`` download endpoint already serves
* one combined ``DRAWING-SET_<version>.pdf`` holding every sheet in order
* one DXF per sheet, named ``<sheet>_<version>.dxf``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from app.application.drawing.drawing_set_service import DrawingSetService
from app.domain.models.drawing import DrawingSet
from app.infrastructure.cad.drawing_sheet_dxf import render_sheet_dxf
from app.infrastructure.config import get_settings
from app.infrastructure.reporting.drawing_set_pdf import (
    write_drawing_set_pdf,
    write_sheet_pdf,
)
from app.domain.models.pem import ProjectEngineeringModel

SET_PDF_PREFIX = "DRAWING-SET"


@dataclass
class SheetGenerationResult:
    drawing_set: DrawingSet
    pdf_paths: list[str] = field(default_factory=list)
    dxf_paths: list[str] = field(default_factory=list)
    set_pdf_path: str | None = None

    @property
    def all_paths(self) -> list[str]:
        paths = list(self.pdf_paths)
        if self.set_pdf_path:
            paths.append(self.set_pdf_path)
        return paths + self.dxf_paths

    def summary(self) -> dict[str, Any]:
        return {
            "drawing_set_id": self.drawing_set.id,
            "sheet_numbers": self.drawing_set.sheet_numbers,
            "sheet_count": len(self.drawing_set.sheets),
            "pdf_count": len(self.pdf_paths),
            "dxf_count": len(self.dxf_paths),
            "set_pdf": self.set_pdf_path,
            "sheets": [
                {
                    "sheet_number": sheet.sheet_number,
                    "title": sheet.title,
                    "discipline": sheet.discipline.value,
                    "scale": sheet.scale,
                    "availability": sheet.availability.value,
                    "view_count": len(sheet.views),
                    "primitive_count": sheet.primitive_count,
                    "geometry_primitive_count": sheet.geometry_primitive_count,
                    "dimension_count": len(sheet.dimensions),
                    "element_ref_count": len(sheet.element_refs),
                    "traceability_coverage": sheet.traceability_coverage,
                    "geometry_signature": sheet.geometry_signature,
                    "missing_data": list(sheet.missing_data),
                }
                for sheet in self.drawing_set.sheets
            ],
        }


class SheetGenerationService:
    def __init__(self, drawing_service: DrawingSetService | None = None) -> None:
        self._drawings = drawing_service or DrawingSetService()

    def generate_project_sheets(
        self,
        project_id: UUID,
        pem: ProjectEngineeringModel,
        *,
        pem_version: int,
    ) -> list[str]:
        """PDF sheet paths, in sheet-number order. Kept for existing callers."""
        return self.generate(project_id, pem, pem_version=pem_version).pdf_paths

    def generate(
        self,
        project_id: UUID,
        pem: ProjectEngineeringModel,
        *,
        pem_version: int,
        snapshot_id: UUID | str | None = None,
        revision: str = "0",
        write_dxf: bool = True,
    ) -> SheetGenerationResult:
        drawing_set = self._drawings.generate(
            pem,
            project_id=project_id,
            pem_version=pem_version,
            snapshot_id=snapshot_id,
            revision=revision,
        )
        output_dir = Path(get_settings().resolved_file_storage_root) / "sheets" / str(project_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        result = SheetGenerationResult(drawing_set=drawing_set)
        for sheet in drawing_set.sheets:
            pdf_path = output_dir / f"{sheet.sheet_number}_{pem_version}.pdf"
            write_sheet_pdf(pdf_path, sheet)
            result.pdf_paths.append(str(pdf_path))
            if write_dxf:
                dxf_path = output_dir / f"{sheet.sheet_number}_{pem_version}.dxf"
                dxf_path.write_text(render_sheet_dxf(sheet).content, encoding="utf-8")
                result.dxf_paths.append(str(dxf_path))

        set_path = output_dir / f"{SET_PDF_PREFIX}_{pem_version}.pdf"
        write_drawing_set_pdf(set_path, drawing_set)
        result.set_pdf_path = str(set_path)
        return result
