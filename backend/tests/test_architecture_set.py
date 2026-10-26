"""Architectural set: program parsing, layout rules, sheets, files, chat interview, Iran defaults."""
from __future__ import annotations

from pathlib import Path

import ezdxf
import pytest

from app.application.architecture import program as prog
from app.application.architecture.build import build_sheets, checks, write_set
from app.application.architecture.layout import generate


def test_parse_persian_prompt():
    p, got = prog.parse("نقشه‌های معماری یک ساختمان ۴ طبقه روی زمین ۱۰×۲۵ بکش")
    assert (p.plot_width_m, p.plot_depth_m, p.floors) == (10, 25, 4)
    assert {"plot", "floors"} <= got


def test_parse_english_prompt():
    p, got = prog.parse("architectural drawings for a 5-storey steel building on a 12x30 plot, 2 units, 3 bedrooms")
    assert (p.plot_width_m, p.plot_depth_m, p.floors, p.units_per_floor, p.bedrooms, p.structure) == (12, 30, 5, 2, 3, "steel")


def test_layout_respects_occupancy_and_rules():
    p, _ = prog.parse("4 floors 10x25")
    L = generate(p)
    assert L.D <= L.rules.occupancy_depth(25) + 1e-6
    assert all(c[3] == "OK" for c in checks(L)), checks(L)
    kinds = {r.kind for f in L.floors for r in f.rooms}
    assert {"living", "kitchen", "bath", "stair", "elevator"} <= kinds
    assert any(o.kind == "door" for f in L.floors for o in f.openings)


def test_configurable_occupancy():
    p, _ = prog.parse("4 floors 10x25 occupancy 50")
    L = generate(p)
    assert L.D <= 0.5 * 25 + L.rules.occupancy_extra_m + 1e-6


def test_sheet_set_contents():
    p, _ = prog.parse("4 floors 10x25")
    _, sheets = build_sheets(p)
    nos = [s.no for s in sheets]
    assert nos[0] == "A-000" and "C-101" in nos and "A-601" in nos
    assert sum(s.kind == "section" for s in sheets) >= 2
    assert sum(s.kind == "elevation" for s in sheets) == 4
    assert sum(s.kind == "plan" for s in sheets) >= 3  # ground, typical, roof
    plan = next(s for s in sheets if s.no == "A-102")
    msp = plan.doc.modelspace()
    layers = {e.dxf.layer for e in msp}
    assert {"A-WALL", "A-DOOR", "A-GLAZ", "A-FURN", "A-AREA-IDEN", "S-AXIS"} <= layers
    assert any(e.dxftype() == "ARC" and e.dxf.layer == "A-DOOR" for e in msp)
    assert any(e.dxftype() == "DIMENSION" for e in msp)
    styles = {s.dxf.font for s in plan.doc.styles}
    assert "tahoma.ttf" in styles and "arial.ttf" in styles


def test_write_set_files(tmp_path: Path):
    p, _ = prog.parse("3 floors 9x20 no parking")
    m = write_set(p, tmp_path, png=False)
    for s in m["sheets"]:
        doc = ezdxf.readfile(tmp_path / s["dxf"])
        assert len(doc.modelspace()) > 10
    assert (tmp_path / "architectural-set.zip").exists()


def test_chat_interview_then_set(tmp_path, monkeypatch):
    from app.application.architecture import service

    monkeypatch.setattr(service, "_root", lambda: tmp_path)
    import pymupdf

    def fake_render(doc, png, width_px=2400):
        d = pymupdf.open(); d.new_page(); png.write_bytes(b"png"); return d.tobytes()

    monkeypatch.setattr("app.application.architecture.build.render", fake_render)
    r = service.chat_turn("نقشه معماری یک ساختمان مسکونی بکش", owner="u", project_id=None, pending=None, save_project_file=None)
    assert r and r[1]["intent"] == "architecture_interview"
    pending = r[1]["arch_interview"]
    r2 = service.chat_turn("زمین ۱۰ در ۲۵، ۴ طبقه", owner="u", project_id=None, pending=pending, save_project_file=None)
    assert r2 and r2[1]["intent"] == "architecture_set"
    assert len(r2[1]["arch_set"]["sheets"]) >= 12
    assert service.chat_turn("what is mabhas 9?", owner="u", project_id=None, pending=None, save_project_file=None) is None


def test_new_projects_default_to_iran():
    from uuid import uuid4

    from app.domain.models.pem import Jurisdiction, UnitSystem, create_initial_pem

    pem = create_initial_pem(uuid4(), "x")
    c = pem.code_configuration
    assert c.jurisdiction == Jurisdiction.IRAN
    assert "Mabhas 9" in c.concrete_edition and "Mabhas 10" in c.steel_edition
    assert "2800" in (c.seismic_edition or "") and "Mabhas 6" in c.loading_edition
    assert pem.unit_configuration.system == UnitSystem.SI_METRIC
    us = create_initial_pem(uuid4(), "y", jurisdiction=Jurisdiction.US)
    assert us.code_configuration.jurisdiction == Jurisdiction.US
