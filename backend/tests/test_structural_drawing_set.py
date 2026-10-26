import ezdxf
import pytest

from app.application.autocad import structural_set as ss
from app.application.frame3d_chat_analysis import (
    build_frame3d_payload,
    parse_frame3d_request,
    run_frame3d_for_export,
)

BASE = {"storeys": 4, "bays_x": 3, "bays_y": 2, "bay_x_m": 5, "bay_y_m": 4, "storey_height_m": 3.2,
        "design_code": "MABHAS9", "foundation": True, "seismic_code": "IRAN_2800"}


@pytest.fixture(scope="module")
def built():
    inp, raw, design = run_frame3d_for_export(BASE)
    return inp, ss.build_structural_set(inp, raw, design, "Test")


def test_sheet_list(built):
    inp, (sheets, notes) = built
    nos = [s.sheet_no for s in sheets]
    assert nos == ["S-101", "S-102", "S-103", "S-104", "S-105", "S-201", "S-301", "S-401", "S-501"]
    assert notes == []


def test_every_sheet_is_valid_dxf_with_title_block(built, tmp_path):
    _, (sheets, _) = built
    for s in sheets:
        p = tmp_path / f"{s.sheet_no}.dxf"
        p.write_text(s.dxf_text(), encoding="utf-8")
        doc = ezdxf.readfile(p)
        assert not doc.audit().has_errors
        layouts = [l for l in doc.layouts if l.name != "Model"]
        assert layouts and "Layout1" not in [l.name for l in layouts]
        layers = {l.dxf.name for l in doc.layers}
        assert {"S-TITLEBLOCK", "S-BORDER", "S-AXIS"} <= layers
        styles = {st.dxf.font for st in doc.styles}
        assert {"arial.ttf", "tahoma.ttf"} <= styles


def test_column_schedule_lists_every_group(built):
    inp, (sheets, _) = built
    txt = " ".join(e.dxf.text for e in sheets[0].doc.modelspace().query("TEXT"))
    for m in ("C1", "C2", "C3"):
        assert m in txt
    assert "Φ10@" in txt and "COLUMN SCHEDULE" in txt


def test_beam_layout_marks_per_storey(built):
    _, (sheets, _) = built
    txt = " ".join(e.dxf.text for e in sheets[2].doc.modelspace().query("TEXT"))
    assert all(m in txt for m in ("B2X1", "B2X2", "B2Y1", "B2Y2"))


@pytest.mark.parametrize("dims", [(1, 1, 1), (6, 4, 2), (2, 5, 3)])
def test_generic_frames(dims):
    st, bx, by = dims
    inp, raw, design = run_frame3d_for_export({**BASE, "storeys": st, "bays_x": bx, "bays_y": by})
    sheets, _ = ss.build_structural_set(inp, raw, design)
    assert len(sheets) == st + 5


def test_needs_design():
    inp, raw, _ = run_frame3d_for_export({**BASE, "design_code": "NONE"})
    with pytest.raises(ValueError):
        ss.build_structural_set(inp, raw, None)


def test_pdf_preview(built):
    pytest.importorskip("pymupdf")
    _, (sheets, _) = built
    pdf = ss.render_pdf(sheets[:2])
    assert pdf[:5] == b"%PDF-"


@pytest.mark.parametrize("q", ["نقشه‌های اجرایی سازه را بده", "نقشه های اجرایی سازه", "دیتیل‌های سازه رو بده",
                               "give me structural detail drawings", "structural drawing set please"])
def test_chat_intent(q):
    assert ss.wants_structural_set(q)


@pytest.mark.parametrize("q", ["نقشه آپارتمان دو خوابه بکش", "3 storey frame 2x2 bays", "convert this pdf to dxf"])
def test_chat_intent_negative(q):
    assert not ss.wants_structural_set(q)


def test_store_and_list(tmp_path, monkeypatch):
    from app.application.autocad import service
    monkeypatch.setattr(service, "_root", lambda: tmp_path)
    saved = []
    meta = ss.generate_and_store(BASE, owner="u1", project_id="p1", with_pdf=False,
                                 save_project_file=lambda n, b, c: saved.append((n, c)) or "f")
    assert len(meta["sheets"]) == 9 and all(it["file_id"] == "f" for it in meta["sheets"])
    assert ss.list_sets("u1", "p1")[0]["id"] == meta["id"]
    assert ss.list_sets("u2") == []
    with pytest.raises(FileNotFoundError):
        ss.set_dir(meta["id"], "u2")
    assert len(service.list_jobs("u1", "p1")) == 9


# ---- Persian frame requests
@pytest.mark.parametrize("q,exp", [
    ("۳ دهانه ۵ متری در جهت x و ۲ دهانه ۴ متری در جهت y، قاب بتنی ۴ طبقه ارتفاع ۳.۲ متر", (4, 3, 2, 5.0, 4.0, 3.2)),
    ("قاب سه دهانه در جهت ایکس به طول ۶ متر و دو دهانه در جهت وای ۴٫۵ متری، پنج طبقه با ارتفاع ۳ متر", (5, 3, 2, 6.0, 4.5, 3.0)),
    ("در جهت x ۴ دهانه ۵ متری و در جهت y ۳ دهانه ۶ متری، ۳ طبقه", (3, 4, 3, 5.0, 6.0, 3.2)),
    ("3x2 bays of 5 m, 4 storeys", (4, 3, 2, 5.0, 5.0, 3.2)),
])
def test_persian_frame_parse(q, exp):
    i = parse_frame3d_request(q)
    assert (i.storeys, i.bays_x, i.bays_y, i.bay_x_m, i.bay_y_m, i.storey_height_m) == exp


def test_persian_missing_question_is_persian():
    r = build_frame3d_payload("یک قاب بتنی ۴ طبقه با ارتفاع ۳ متر")
    assert r["status"] == "MISSING_REQUIRED_INPUT"
    assert "لطفاً" in r["message"] and "Please" not in r["message"]
