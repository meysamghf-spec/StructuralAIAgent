import io

import ezdxf

from app.application import drawing_standard as ds
from app.application import frame3d_chat_analysis as f3
from app.application.structural_drawings import build_structural_doc

REQ = "3-storey RC moment frame, 3x2 bays of 5 m, storey height 3.2 m, Iran 2800, design to Mabhas 9, foundation"


def _run():
    p = f3.build_frame3d_payload(REQ)
    return f3.run_frame3d_for_export({**p["inputs"], "_p": p["parsed_from_request"]})


def test_persian_is_shaped_and_latin_untouched():
    out = ds.fa("پلان طبقه")
    assert out != "پلان طبقه" and any("\ufb50" <= c <= "\ufeff" for c in out)
    assert ds.fa("STORY 1") == "STORY 1"


def test_pro_drawing_set_audits_clean_with_layouts_title_blocks_dims_hatches():
    inp, raw, design = _run()
    doc, sheets = build_structural_doc(inp, raw, design)
    assert ds.audit(doc) == 0
    assert sheets[:4] == ["S-01", "S-02", "S-03", "S-10"] and "S-F1" in sheets
    assert {"E-A", "E-B", "E-C", "E-1", "E-4"} <= set(sheets)
    for name in sheets:
        lay = doc.layouts.get(name)
        assert lay.query("VIEWPORT") and lay.query('LWPOLYLINE[layer=="S-BORDER"]')
        texts = " ".join(t.dxf.text for t in lay.query("TEXT"))
        assert "LOGO" in texts and "1:" in texts and name in texts
    msp = doc.modelspace()
    assert len(msp.query("DIMENSION")) > 20
    assert msp.query('HATCH[layer=="S-CONC-HATCH"]') and msp.query('HATCH[layer=="S-FOOT-HATCH"]')
    assert doc.layers.get("S-AXIS").dxf.linetype == "CENTER" and doc.layers.get("S-CONC").dxf.lineweight == 50
    tags = {t.dxf.text.split()[0] for t in msp.query('TEXT[layer=="S-TAG"]')}
    assert {"C1", "C2", "C3", "B1", "B3", "F1"} <= tags
    levels = {t.dxf.text for t in msp.query('TEXT[layer=="S-LEVEL"]')}
    assert {"±0.00", "+3.20", "+9.60"} <= levels
    assert any(t.dxf.style == ds.PERSIAN for t in msp.query("TEXT"))


def test_round_trip_through_export_text():
    inp, raw, design = _run()
    from app.application import csi_text_export as cte

    doc = ezdxf.read(io.StringIO(cte.build_export("dxf_plans", inp, raw, design)))
    assert ds.audit(doc) == 0


def test_foundation_detailing_sheet_and_chat_commands():
    from app.application import detailing_assumptions as da
    from app.application.foundation_detailing import build_foundation_doc

    assert f3.requested_export_formats("نقشه فونداسیون") == ["dxf_foundation"]
    assert f3.requested_foundation_view("فونداسیون را نشان بده") and f3.requested_foundation_view("show foundation")
    assert da.parse_assumptions("پوشش پی ۶۰ میلیمتر")[0] == {"footing_cover_mm": 60.0}
    inp, raw, design = _run()
    doc, rows, total = build_foundation_doc(inp, raw, design)
    assert ds.audit(doc) == 0 and total > 0
    assert {r["mark"] for r in rows} >= {"F1-X", "F1-Y", "F1-S"}
    for name in ("FD-01", "FD-02"):
        assert doc.layouts.get(name).query("VIEWPORT")
    texts = " ".join(t.dxf.text for t in doc.modelspace().query("TEXT"))
    assert "SECTION F1-F1" in texts and "lean concrete" in texts and "90° hook" in texts
    f = raw["foundation_design"]["footings"][0]
    assert {"P_kn", "DC_punching", "bars"} <= set(f)
    p = f3.build_frame3d_payload("فونداسیون را نشان بده", prior_spec={**f3.build_frame3d_payload(REQ)["inputs"]})
    assert p["show_foundation"] is True and p["viewer"]["footings"]
