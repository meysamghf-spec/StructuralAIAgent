"""Prompt -> floor plan sheet (A-101) via the existing brief parser + layout generator."""
from __future__ import annotations

from typing import Any

from app.application.building_brief_parser import BuildingBriefParser
from app.application.building_layout_generator import BuildingLayoutGenerator

from .standards import SheetType, add_title_block, setup_doc


def _v(x):
    return getattr(x, "value", x)


def generate_from_prompt(prompt: str) -> tuple[Any, dict[str, Any]]:
    brief = BuildingBriefParser().parse(prompt)
    result = BuildingLayoutGenerator().generate(brief)
    model = result.building_model
    plans = model.floor_plans
    plan = plans[1] if len(plans) > 1 else plans[0]  # typical floor
    doc = setup_doc()
    msp = doc.modelspace()
    pts = [(p.x, p.y) for p in plan.boundary.points]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)

    for wall in plan.walls:
        layer = "A-WALL-EXTR" if _v(wall.wall_type) == "EXTERIOR" else "A-WALL"
        msp.add_line((wall.start.x, wall.start.y), (wall.end.x, wall.end.y), dxfattribs={"layer": layer})
    for sp in plan.spaces:
        sp_pts = [(p.x, p.y) for p in sp.boundary.points]
        layer = "A-FLOR-STRS" if _v(sp.usage) == "STAIR" else "A-AREA"
        msp.add_lwpolyline(sp_pts, close=True, dxfattribs={"layer": layer})
        cx = sum(p[0] for p in sp_pts) / len(sp_pts); cy = sum(p[1] for p in sp_pts) / len(sp_pts)
        msp.add_text(sp.name, height=0.3, dxfattribs={"layer": "A-AREA-IDEN"}).set_placement((cx - 0.8, cy + 0.1))
        msp.add_text(f"{sp.boundary.area:.1f} m2", height=0.22, dxfattribs={"layer": "A-AREA-IDEN"}).set_placement((cx - 0.8, cy - 0.35))
    for d in plan.doors:
        msp.add_circle((d.center.x, d.center.y), d.width_m / 2, dxfattribs={"layer": "A-DOOR"})
    for wdw in getattr(plan, "windows", []) or []:
        c = getattr(wdw, "center", None)
        if c is not None:
            msp.add_circle((c.x, c.y), getattr(wdw, "width_m", 1.0) / 2, dxfattribs={"layer": "A-GLAZ"})
    # simple structural grid at ~ <=5 m bays
    import math
    for axis, lo, hi, olo, ohi in (("x", x0, x1, y0, y1), ("y", y0, y1, x0, x1)):
        n = max(1, math.ceil((hi - lo) / 5.0))
        for i in range(n + 1):
            v = lo + (hi - lo) * i / n
            a, b = ((v, olo - 1), (v, ohi + 1)) if axis == "x" else ((olo - 1, v), (ohi + 1, v))
            msp.add_line(a, b, dxfattribs={"layer": "S-GRID", "linetype": "DASHED"})
            label = chr(65 + i) if axis == "x" else str(i + 1)
            msp.add_text(label, height=0.4, dxfattribs={"layer": "S-GRID"}).set_placement((a[0] - 0.2, a[1] - 0.6) if axis == "x" else (a[0] - 0.8, a[1] - 0.2))
    # overall dimensions as text
    msp.add_text(f"{x1 - x0:.2f} m", height=0.35, dxfattribs={"layer": "A-ANNO-DIMS"}).set_placement(((x0 + x1) / 2 - 0.6, y0 - 1.8))
    msp.add_text(f"{y1 - y0:.2f} m", height=0.35, dxfattribs={"layer": "A-ANNO-DIMS"}).set_placement((x1 + 1.3, (y0 + y1) / 2))
    add_title_block(msp, x0 - 1.5, y0 - 2.2, x1 + 2.5, y1 + 1.2, title=f"{plan.name} - floor plan",
                    sheet_no=SheetType.FLOOR_PLAN.value, notes=f"{model.floor_count} floors, {plan.gross_area_m2:.0f} m2/floor, scale 1:100")
    summary = {
        "sheet": SheetType.FLOOR_PLAN.value,
        "floor_count": model.floor_count,
        "floor_name": plan.name,
        "footprint_m": [round(x1 - x0, 2), round(y1 - y0, 2)],
        "spaces": len(plan.spaces), "walls": len(plan.walls), "doors": len(plan.doors),
        "assumptions": list(result.assumptions)[:8] + list(model.generation_assumptions)[:5],
        "warnings": list(result.warnings)[:8],
    }
    return doc, summary
