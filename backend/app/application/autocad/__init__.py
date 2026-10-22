"""AutoCAD (DXF) integration v1: prompt->drawing and PDF/image->DXF.

Pipeline is sheet-based so later phases (all floor plans, roof, site,
elevations, sections, stair details, schedules per Mabhas 4 + municipal
rules) plug in as new SheetType renderers without changing storage,
layers, title block or the API.
"""
