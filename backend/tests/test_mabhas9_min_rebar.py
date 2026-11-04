"""pt616u: every member (also NG) carries reinforcement; NG members get a suggested passing section."""
import math
import re

from app.application import mabhas9_rc_design as m9

BAR = re.compile(r"^(\d+)Φ(\d+)$")


def _beam(M, b=300, h=400):
    return m9.design_beam(m_neg_end=M, m_pos_end=M / 2, m_pos_mid=M / 2, vu=150, b=b, h=h, fc=25, fy=400)


def test_passing_beam_unchanged_basis():
    d = _beam(50)
    assert d["status"] == "PASS" and d["rebar_basis"] == "DESIGN" and d["suggested_section"] is None


def test_ng_beam_section_too_small_gets_max_one_layer_bars_stirrups_and_suggestion():
    d = _beam(400)
    assert d["status"] == "FAIL" and d["rebar_basis"] == "MAX_FEASIBLE"
    n, db = map(int, BAR.match(d["top_bars"]).groups())
    assert n >= 2 and (n, db, n * m9.bar_area(db)) == m9.beam_max_one_layer(300)  # same rule as detailing fill (#79)
    assert BAR.match(d["bottom_bars"]) and "Φ10@" in d["shear"]["stirrups"]
    assert math.isfinite(d["DC_flexure"]) and d["DC_flexure"] > 1
    sug = d["suggested_section"]
    assert sug and sug["h_mm"] > 400
    chk = _beam(400, b=sug["b_mm"], h=sug["h_mm"])
    assert chk["status"] == "PASS"


def test_ng_beam_bottom_at_least_min():
    d = _beam(2000)
    as_bot = d["As_bot_mm2"]
    assert as_bot >= d["As_min_mm2"] and math.isfinite(d["DC_flexure"])


def test_ng_column_keeps_bars_ties_and_suggests():
    r = {"c1": [{"combo": "x", "P": 9000, "ends": [(300, 200)]}]}
    for size in (300, 200):
        d = m9.design_column_group(r, size, size, 25, 400, 2800)
        assert d["status"] == "FAIL" and d["rebar_basis"] in ("MAX_FEASIBLE", "MINIMUM")
        assert BAR.match(d["bars"]) and "Φ10@" in d["ties"]["text"] and math.isfinite(d["DC"])
        assert d["suggested_section"] and d["suggested_section"]["b_mm"] > size


def test_light_column_gets_one_percent_minimum():
    r = {"c1": [{"combo": "x", "P": 50, "ends": [(1, 1)]}]}
    d = m9.design_column_group(r, 400, 400, 25, 400, 2800)
    assert d["status"] == "PASS" and d["rho"] >= 0.01 and d["rebar_basis"] == "DESIGN"
