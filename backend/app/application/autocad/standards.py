"""Layer standard, sheet registry and title block shared by all sheets."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# AIA/NCS-style layer names: (color index, lineweight 1/100 mm, description)
LAYERS: dict[str, tuple[int, int, str]] = {
    "A-WALL": (7, 50, "Walls"),
    "A-WALL-EXTR": (7, 70, "Exterior walls"),
    "A-DOOR": (3, 25, "Doors"),
    "A-GLAZ": (4, 25, "Windows / glazing"),
    "A-AREA-IDEN": (2, 18, "Room names and areas"),
    "A-AREA": (8, 13, "Room boundaries"),
    "A-FLOR-STRS": (6, 25, "Stairs"),
    "A-ANNO-DIMS": (1, 18, "Dimensions"),
    "A-ANNO-TTLB": (7, 35, "Title block"),
    "A-ROOF": (5, 35, "Roof (later phase)"),
    "A-ELEV": (7, 35, "Elevations (later phase)"),
    "A-SECT": (7, 35, "Sections (later phase)"),
    "A-SCHD": (7, 18, "Schedules (later phase)"),
    "C-SITE": (94, 25, "Site plan (later phase)"),
    "S-GRID": (8, 13, "Structural grid"),
    "S-COLS": (1, 50, "Columns"),
    "X-VECT-MAJR": (7, 50, "Vectorized long lines (likely walls)"),
    "X-VECT-MINR": (8, 18, "Vectorized short lines / detail"),
    "X-VECT-TEXT": (2, 18, "Vectorized text (PDF only)"),
}


class SheetType(str, Enum):
    FLOOR_PLAN = "A-101"
    ROOF_PLAN = "A-201"
    SITE_PLAN = "C-101"
    ELEVATION = "A-301"
    SECTION = "A-401"
    STAIR_DETAIL = "A-501"
    DOOR_WINDOW_SCHEDULE = "A-601"
    FINISH_SCHEDULE = "A-602"
    VECTORIZED = "X-001"


@dataclass(frozen=True)
class SheetSpec:
    type: SheetType
    title: str
    implemented: bool


SHEET_REGISTRY: list[SheetSpec] = [
    SheetSpec(SheetType.FLOOR_PLAN, "Floor plan", True),
    SheetSpec(SheetType.VECTORIZED, "Vectorized drawing", True),
    SheetSpec(SheetType.ROOF_PLAN, "Roof plan", False),
    SheetSpec(SheetType.SITE_PLAN, "Site plan", False),
    SheetSpec(SheetType.ELEVATION, "Elevations", False),
    SheetSpec(SheetType.SECTION, "Sections", False),
    SheetSpec(SheetType.STAIR_DETAIL, "Stair details", False),
    SheetSpec(SheetType.DOOR_WINDOW_SCHEDULE, "Door/window schedule", False),
    SheetSpec(SheetType.FINISH_SCHEDULE, "Finish schedule", False),
]


def setup_doc():
    import ezdxf

    doc = ezdxf.new("R2010", setup=True)
    doc.units = 6  # meters
    for name, (color, lw, desc) in LAYERS.items():
        layer = doc.layers.add(name, color=color)
        layer.dxf.lineweight = lw
        layer.description = desc
    return doc


def add_title_block(msp, x0, y0, x1, y1, *, title, sheet_no, notes=""):
    """Border + title block strip below the drawing extents (model space)."""
    w, h = x1 - x0, y1 - y0
    pad = max(w, h) * 0.08 + 0.5
    bx0, by0, bx1, by1 = x0 - pad, y0 - pad * 2.2, x1 + pad, y1 + pad
    attrs = {"layer": "A-ANNO-TTLB"}
    msp.add_lwpolyline([(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)], close=True, dxfattribs=attrs)
    tb = by0 + pad * 1.1
    msp.add_line((bx0, tb), (bx1, tb), dxfattribs=attrs)
    th = pad * 0.25
    msp.add_text(f"{sheet_no}  {title}", height=th, dxfattribs=attrs).set_placement((bx0 + pad * 0.3, by0 + pad * 0.6))
    msp.add_text(f"StructuralAI  |  {notes}"[:120], height=th * 0.6, dxfattribs=attrs).set_placement((bx0 + pad * 0.3, by0 + pad * 0.2))
    return (bx0, by0, bx1, by1)
