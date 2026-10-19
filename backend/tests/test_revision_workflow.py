"""Generic approval/revision workflow + assumptions registry across two structure types (RC frame, AISC steel beam)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.application import assumptions_registry as reg
from app.application import engineering_modules as em
from app.application import revision_workflow as rw
from app.application.frame3d_chat_analysis import build_frame3d_payload


class FakeApprovals:
    def __init__(self):
        self.items = []

    def create_request(self, project_id, **kw):
        item = SimpleNamespace(id=uuid4(), project_id=project_id, **kw)
        self.items.append(item)
        return item


FRAME = {"storeys": 2, "bays_x": 2, "bays_y": 1, "bay_x_m": 5, "bay_y_m": 4, "storey_height_m": 3.2, "design_code": "MABHAS9"}
STEEL = {"kind": "aisc_steel_beam"}


def _steel_payload():
    return em.adapter_for("aisc_steel_beam").run({"span_m": 8, "uniform_load_kn_m": 20, "fy_ksi": 50, "zx_in3": 60})


def test_registry_is_module_agnostic():
    assert {"rebar_detailing", "mabhas9", "iran2800", "foundation", "aisc360"} <= set(reg.modules())
    parsed, errors = reg.parse("cover 50 mm, Fy = 60 ksi, Zx = 90, allowable bearing 200 kPa", ["rebar_detailing", "aisc360", "foundation"])
    assert parsed == {"rebar_detailing": {"cover_mm": 50.0}, "aisc360": {"fy_ksi": 60.0, "zx_in3": 90.0},
                      "foundation": {"allowable_bearing_kpa": 200.0}}
    _, errors = reg.parse("cover 500 mm", ["rebar_detailing"])
    assert errors and "outside" in errors[0]


def test_two_structure_types_create_approvals_and_revise_on_reject():
    approvals, pid = FakeApprovals(), uuid4()
    frame = build_frame3d_payload("", manual_inputs=FRAME)
    steel = _steel_payload()
    a1 = rw.create_run_approval(approvals, pid, "u1", frame)
    s1 = rw.create_run_approval(approvals, pid, "u1", steel)
    assert a1.metadata["module_kind"] == "frame3d_analysis" and s1.metadata["module_kind"] == "aisc_steel_beam"
    assert a1.metadata["revision"] == 1 and "3D frame" in a1.summary and "AISC" in s1.summary

    # RC frame: reason in Persian -> column size up + cover change -> rev 2 linked to rev 1 with a diff
    out = rw.handle_rejection(approvals, pid, a1, "ابعاد ستون را افزایش بده، پوشش ۵۰ میلی‌متر", "u1")
    assert out["outcome"] == "revised"
    a2 = out["approval"]
    assert a2.metadata["revision"] == 2 and a2.metadata["parent_approval_id"] == str(a1.id)
    keys = {c["key"]: c for c in a2.metadata["changes"]}
    assert keys["column_b_m"]["new"] == 0.45 and keys["assumptions.cover_mm"]["new"] == 50.0
    # rev 3 chain keeps the root
    a3 = rw.handle_rejection(approvals, pid, a2, "use Φ20 for columns", "u1")["approval"]
    assert a3.metadata["revision"] == 3 and a3.metadata["root_approval_id"] == str(a1.id)
    assert a3.metadata["inputs"]["assumptions"]["column_bars"] == [20]

    # Steel beam: same workflow, different module
    out = rw.handle_rejection(approvals, pid, s1, "section too small, increase it", "u1")
    assert out["outcome"] == "revised" and out["approval"].metadata["inputs"]["zx_in3"] == 75.0
    out = rw.handle_rejection(approvals, pid, s1, "Fy = 65 ksi", "u1")
    assert out["approval"].metadata["inputs"]["fy_ksi"] == 65.0


def test_unparseable_reason_asks_for_clarification():
    approvals, pid = FakeApprovals(), uuid4()
    a1 = rw.create_run_approval(approvals, pid, "u1", build_frame3d_payload("", manual_inputs=FRAME))
    out = rw.handle_rejection(approvals, pid, a1, "I don't like it", "u1")
    assert out["outcome"] == "clarify" and "column" in out["message"]
    other = SimpleNamespace(id=uuid4(), target_action="agent.run", metadata={})
    assert rw.handle_rejection(approvals, pid, other, "x", "u1")["outcome"] == "not_applicable"


def test_drift_intent():
    adapter = em.adapter_for("frame3d_analysis")
    inp, a, _ = em.parse_changes(adapter, "drift too high", {"column_b_m": 0.4, "column_h_m": 0.4, "beam_h_m": 0.45})
    assert inp == {"column_b_m": 0.45, "column_h_m": 0.45, "beam_h_m": 0.5} and a == {}
