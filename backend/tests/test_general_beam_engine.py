from app.application.general_beam_engine import CAPABILITIES_MESSAGE, analyze_beam_prompt


def test_simply_supported_rc_beam_en():
    r = analyze_beam_prompt("Analyze a simply supported reinforced concrete beam with a 6 m span and uniform load of 20 kN/m.")
    assert r["payload"]["results"]["max_moment_kn_m"] == 90.0
    assert r["payload"]["results"]["max_shear_kn"] == 60.0
    assert r["payload"]["design"]["status"] in {"PASS", "FAIL"}


def test_simply_supported_rc_beam_fa():
    r = analyze_beam_prompt("تیر ساده بتن مسلح با دهانه ۶ متر و بار گسترده ۲۰ کیلونیوتن بر متر را تحلیل کن")
    assert r["payload"]["results"]["max_moment_kn_m"] == 90.0


def test_cantilever_point_load():
    r = analyze_beam_prompt("cantilever beam 3 m with point load 10 kN")
    assert r["payload"]["results"]["max_moment_kn_m"] == 30.0


def test_non_beam_returns_none():
    assert analyze_beam_prompt("hello there") is None
    assert "{" not in CAPABILITIES_MESSAGE.split("\n")[0]
