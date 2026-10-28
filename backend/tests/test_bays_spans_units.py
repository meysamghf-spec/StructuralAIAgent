"""Bay counts / spans: phrasing matrix, units, required-never-guessed rule, legacy loading, /frame3d/run validation,
orchestrator defaults, and the drawings fallback to the latest *complete* run."""
from __future__ import annotations

import json
import types
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.application import frame3d_chat_analysis as f3
from app.application import frame3d_followup as fu
from app.application.chat_runs import is_usable_frame_run, pick_usable_frame_run
from app.application.frame3d_bays import parse_bays
from app.application.length_units import parse_length_m, to_metres

PAYLOAD_FAST = dict(with_modal=False, with_foundation=False)


def _quick(monkeypatch):
    real = f3.run_frame3d
    monkeypatch.setattr(f3, "run_frame3d", lambda inp, **kw: real(inp, **PAYLOAD_FAST))


# ------------------------------------------------------------------------------------------ units
@pytest.mark.parametrize("text,expected", [
    ("5", 5.0), ("5 m", 5.0), ("600 cm", 6.0), ("6000 mm", 6.0), ("20 ft", 6.096), ("۶۰۰ سانتی‌متر", 6.0),
    ("۶۰۰۰ میلی‌متر", 6.0), ("۴٫۵ متر", 4.5), ("4,5 m", 4.5), ("۵ متری", 5.0), ("236.22 inch", 6.0),
])
def test_any_length_unit_is_converted_to_metres(text, expected):
    assert parse_length_m(text) == pytest.approx(expected, rel=1e-3)


def test_to_metres_default_is_metres():
    assert to_metres(5, None) == 5.0 and to_metres(5, "cm") == 0.05 and to_metres(10, "mm") == 0.01


# ------------------------------------------------------------------------------------------ phrasing matrix
@pytest.mark.parametrize("text,counts,spans", [
    ("تعداد دهانه در جهت x برابر ۲ و در جهت y برابر ۱، دو طبقه، طراحی کن", {"bays_x": 2, "bays_y": 1}, {}),
    ("2 bays in x and 1 bay in y, 2 storeys, design it", {"bays_x": 2, "bays_y": 1}, {}),
    ("3 bays of 5 m in x and 2 bays of 4 m in y", {"bays_x": 3, "bays_y": 2}, {"bay_x_m": 5.0, "bay_y_m": 4.0}),
    ("۳ دهانه ۵ متری در جهت x و ۲ دهانه ۴ متری در جهت y", {"bays_x": 3, "bays_y": 2}, {"bay_x_m": 5.0, "bay_y_m": 4.0}),
    ("۲ در x و ۱ در y", {"bays_x": 2, "bays_y": 1}, {}),
    ("x=2, y=1", {"bays_x": 2, "bays_y": 1}, {}),
    ("2x3 bays of 5 m", {"bays_x": 2, "bays_y": 3}, {"bay_x_m": 5.0, "bay_y_m": 5.0}),
    ("۳×۲ دهانه", {"bays_x": 3, "bays_y": 2}, {}),
    ("bays_x = 2 bays_y = 3", {"bays_x": 2, "bays_y": 3}, {}),
    ("3 bays in each direction", {"bays_x": 3, "bays_y": 3}, {}),
    ("قاب ۳ طبقه ۲ دهانه در هر دو جهت", {"bays_x": 2, "bays_y": 2}, {}),
    ("دهانه x ۶۰۰ سانتی‌متر و دهانه y ۴۵۰۰ میلی‌متر", {}, {"bay_x_m": 6.0, "bay_y_m": 4.5}),
    ("span in y: 600 cm", {}, {"bay_y_m": 6.0}),
    ("طول دهانه در جهت x برابر ۶ متر", {}, {"bay_x_m": 6.0}),
    ("3 bays x 5 m, 2 bays y 4 m, 4 storeys 3.2 m", {"bays_x": 3, "bays_y": 2}, {"bay_x_m": 5.0, "bay_y_m": 4.0}),
    ("قاب سه دهانه در جهت ایکس به طول ۶ متر و دو دهانه در جهت وای ۴٫۵ متری، پنج طبقه با ارتفاع ۳ متر",
     {"bays_x": 3, "bays_y": 2}, {"bay_x_m": 6.0, "bay_y_m": 4.5}),
])
def test_phrasing_matrix(text, counts, spans):
    r = parse_bays(text)
    assert r.counts == counts and r.spans == spans


def test_lone_bare_count_is_ambiguous():
    r = parse_bays("2 bays")
    assert not r.counts and r.ambiguous == 2


@pytest.mark.parametrize("text", ["یک قاب دو دهنه، دو طبقه را طراحی کن", "design a 2-bay 2-storey frame", "a 5-storey frame with 3 bays"])
def test_bare_count_without_direction_asks_for_the_direction(text):
    r = parse_bays(text)
    assert not r.counts and r.ambiguous is not None
    p = f3.build_frame3d_payload(text)
    assert p["status"] == "MISSING_REQUIRED_INPUT"
    assert "x" in p["message"] and "bays_x" not in p["message"]


def test_two_bay_two_storey_flow_remembers_storeys_and_accepts_short_followup(monkeypatch):
    _quick(monkeypatch)
    first = "یک قاب دو دهنه، دو طبقه را طراحی کن"
    p1 = f3.build_frame3d_payload(first)
    assert p1["status"] == "MISSING_REQUIRED_INPUT"
    merged = fu.merge_with_pending("۲ در x و ۱ در y، دهانه‌ها ۵ متری", [first])
    p2 = f3.build_frame3d_payload(merged)
    assert p2["status"] == "completed", p2.get("message")
    i = p2["inputs"]
    assert (i["storeys"], i["bays_x"], i["bays_y"], i["bay_x_m"], i["bay_y_m"]) == (2, 2, 1, 5.0, 5.0)


def test_direction_followup_resolves_pending_count():
    merged = fu.merge_with_pending("x", ["design a 2-bay 2-storey frame"])
    inp = f3.parse_frame3d_request(merged)
    assert inp.bays_x == 2 and inp.storeys == 2


# ------------------------------------------------------------------------------------------ required / never guessed
def test_spans_are_required_and_not_silently_defaulted():
    inp = f3.parse_frame3d_request("3 طبقه، ۲×۲ دهانه")
    assert set(f3.missing_inputs(inp)) == {"bay_x_m", "bay_y_m"}
    p = f3.build_frame3d_payload("3-storey 2x2 bays")
    assert p["status"] == "MISSING_REQUIRED_INPUT" and "bay_x_m" in p["missing_inputs"]
    assert "bay_x_m" not in p["message"] and "bays_x" not in p["message"]  # friendly labels only


def test_cm_and_mm_are_converted_not_read_as_counts():
    inp = f3.parse_frame3d_request("3-storey 2x2 bays, span x 600 cm, span y 4500 mm")
    assert (inp.bays_x, inp.bays_y, inp.bay_x_m, inp.bay_y_m) == (2, 2, 6.0, 4.5)
    assert not f3.missing_inputs(inp)
    inp = f3.parse_frame3d_request("3 storeys, 2 bays in x, 3 bays in y, 600 cm spans")
    assert (inp.bays_x, inp.bays_y, inp.bay_x_m, inp.bay_y_m) == (2, 3, 6.0, 6.0)


def test_assume_defaults_allows_5m_spans_and_states_them(monkeypatch):
    _quick(monkeypatch)
    p = f3.build_frame3d_payload(fu.merge_with_pending("فرض کن", ["یک قاب سه بعدی بتنی تحلیل کن"]))
    assert p["status"] == "completed"
    assumed = " ".join(p["assumed_defaults"])
    assert "bay_x_m" in assumed or "دهانه" in assumed or "span" in assumed.lower()
    assert p["inputs"]["bay_x_m"] == 5.0


def test_span_range_is_enforced_in_chat_payload():
    p = f3.build_frame3d_payload("2 storeys, 2x2 bays of 40 m")
    assert p["status"] != "completed"


# ------------------------------------------------------------------------------------------ legacy / stored data
def test_old_stored_spec_still_loads_with_spans_counted_as_given():
    old = {"storeys": 3, "bays_x": 2, "bays_y": 2, "bay_x_m": 5.0, "bay_y_m": 5.0, "_p": ["storeys", "bays_x", "bays_y"]}
    assert f3.missing_inputs(f3.inputs_from_dict(old)) == []
    plain = {"storeys": 3, "bays_x": 2, "bays_y": 2, "bay_x_m": 5.0, "bay_y_m": 6.0}
    assert f3.missing_inputs(f3.inputs_from_dict(plain)) == []
    inp, raw, design = f3.run_frame3d_for_export(plain)
    assert inp.bay_y_m == 6.0 and raw


def test_incomplete_export_inputs_give_a_readable_error():
    with pytest.raises(ValueError) as e:
        f3.run_frame3d_for_export({"storeys": 2, "bays_x": None, "bays_y": None})
    msg = str(e.value)
    assert "bays_x" not in msg and "تعداد دهانه x" in msg and "Number of bays" in msg or "bays in X" in msg


# ------------------------------------------------------------------------------------------ /frame3d/run validation
def _run(inputs, **kw):
    from app.api.routes import frame3d as route

    return route.run_frame3d_manual(route.Frame3dRunRequest(inputs=inputs, **kw), types.SimpleNamespace(account_id=None))


@pytest.mark.parametrize("v", [0.6, 1.4, 15.5, 600, 6000])
def test_run_rejects_spans_outside_1_5_to_15_m(v):
    with pytest.raises(HTTPException) as e:
        _run({"storeys": 2, "bays_x": 2, "bays_y": 2, "bay_x_m": v, "bay_y_m": 5})
    assert e.value.status_code == 422 and "metres" in e.value.detail and "cm" in e.value.detail


# ------------------------------------------------------------------------------------------ orchestrator tools
def test_orchestrator_asks_instead_of_defaulting_spans():
    from app.application.orchestrator import tools

    props = tools._ANALYZE_PROPS
    assert props["bay_x_m"]["type"] == "number" and "required" in props["bay_x_m"]["description"]
    assert "ONLY when the user explicitly" in props["assume_defaults"]["description"]


# ------------------------------------------------------------------------------------------ drawings fallback
def _run_rec(minutes, status, inputs, label="3D frame analysis"):
    t = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc) + timedelta(minutes=minutes)
    return {"kind": "frame3d_analysis", "status": status, "inputs": inputs, "label": label, "created_at": t.isoformat(),
            "message_id": f"m{minutes}", "conversation_id": "c1", "conversation_title": "t"}


COMPLETE = {"storeys": 3, "bays_x": 2, "bays_y": 2, "bay_x_m": 5.0, "bay_y_m": 5.0, "storey_height_m": 3.2}
INCOMPLETE = {"storeys": 2, "bays_x": None, "bays_y": None, "bay_x_m": None, "bay_y_m": None}


def test_pick_usable_skips_newer_incomplete_runs():
    runs = [_run_rec(1, "completed", COMPLETE), _run_rec(5, "MISSING_REQUIRED_INPUT", INCOMPLETE), _run_rec(6, "completed", INCOMPLETE)]
    assert pick_usable_frame_run(runs)["message_id"] == "m1"
    assert not is_usable_frame_run(_run_rec(2, "FAILED", COMPLETE))
    assert not is_usable_frame_run(_run_rec(2, "UNSUPPORTED_SIZE", COMPLETE))
    assert pick_usable_frame_run([_run_rec(5, "MISSING_REQUIRED_INPUT", INCOMPLETE)]) is None


class _Conv:
    def __init__(self, runs):
        self._runs = runs

    def list_project_chat_runs(self, account, project_id):
        return self._runs


class _Files:
    def ingest_upload(self, *a, **k):  # pragma: no cover
        return types.SimpleNamespace(id="f")


class _Access:
    def require_project(self, pid, acc):
        return types.SimpleNamespace(name="P")


PID = "00000000-0000-0000-0000-000000000001"
ACC = types.SimpleNamespace(account_id="a1")


def _structural_set(monkeypatch, runs, inputs=None):
    from app.api.routes import autocad
    from app.application.autocad import structural_set as ss

    seen = {}

    def fake(inp, **kw):
        seen["inputs"] = inp
        return {"id": "s1"}

    monkeypatch.setattr(ss, "generate_and_store", fake)
    out = autocad.structural_set(autocad.StructuralSetBody(project_id=PID, inputs=inputs), ACC, _Conv(runs), _Files(), _Access())
    return out, seen


def test_structural_set_uses_latest_complete_run_when_newer_run_is_incomplete(monkeypatch):
    runs = [_run_rec(9, "MISSING_REQUIRED_INPUT", INCOMPLETE), _run_rec(1, "completed", COMPLETE)]
    out, seen = _structural_set(monkeypatch, runs)
    assert seen["inputs"]["bays_x"] == 2 and out["built_from"]["message_id"] == "m1"


def test_structural_set_only_incomplete_runs_gives_409_readable(monkeypatch):
    with pytest.raises(HTTPException) as e:
        _structural_set(monkeypatch, [_run_rec(9, "MISSING_REQUIRED_INPUT", INCOMPLETE)])
    assert e.value.status_code in (409, 422) and "bays_x" not in str(e.value.detail) and "مدل" in str(e.value.detail)


def test_structural_set_body_inputs_are_used_and_validated(monkeypatch):
    runs = [_run_rec(1, "completed", COMPLETE)]
    mine = {**COMPLETE, "bays_x": 4, "lang": "fa"}
    out, seen = _structural_set(monkeypatch, runs, inputs=mine)
    assert seen["inputs"]["bays_x"] == 4
    with pytest.raises(HTTPException) as e:
        _structural_set(monkeypatch, runs, inputs={**COMPLETE, "bays_y": None, "bay_y_m": None, "lang": "fa"})
    assert e.value.status_code == 422
    d = e.value.detail
    assert "تعداد دهانه y" in d and "طول دهانه y" in d and "bays_y" not in d


def test_download_resolve_skips_incomplete_runs(monkeypatch):
    from app.api.routes import frame3d as route

    runs = [_run_rec(9, "MISSING_REQUIRED_INPUT", INCOMPLETE), _run_rec(1, "completed", COMPLETE)]
    body = types.SimpleNamespace(project_id=PID, inputs=None)
    monkeypatch.setattr(route.billing, "check_frame_size", lambda a, i: None)
    assert route._resolve(body, ACC, _Conv(runs), _Access())["bays_x"] == 2
    with pytest.raises(HTTPException):
        route._resolve(body, ACC, _Conv([runs[0]]), _Access())
    with pytest.raises(HTTPException) as e:
        route._resolve(types.SimpleNamespace(project_id=PID, inputs={**COMPLETE, "bays_x": None}), ACC, _Conv(runs), _Access())
    assert e.value.status_code == 422


def test_conversation_latest_frame_inputs_skips_incomplete(monkeypatch):
    from app.application import chat_runs
    from app.application.conversation_service import ConversationService

    runs = [_run_rec(9, "MISSING_REQUIRED_INPUT", INCOMPLETE), _run_rec(1, "completed", COMPLETE)]
    monkeypatch.setattr(chat_runs, "extract_runs", lambda conv, msgs: list(runs))
    svc = ConversationService.__new__(ConversationService)
    svc._repo = types.SimpleNamespace(list_messages=lambda cid: [])
    conv = types.SimpleNamespace(id="c", project_id=None)
    assert svc._latest_frame_inputs(conv, ACC)["bays_x"] == 2
