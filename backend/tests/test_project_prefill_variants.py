"""Prefill of the Quick 3D / analysis forms must work for every project and phrasing (not only Project 3)."""
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.optimization_full.model_resolver import inputs_from_texts, resolve_project_frame

CASES = [
    ("ساختمان ۵ طبقه با ۴ دهنه ۶ متری در جهت x و ۳ دهنه ۵ متری در جهت y ارتفاع طبقه ۳.۲ متر",
     dict(storeys=5, bays_x=4, bays_y=3, bay_x_m=6.0, bay_y_m=5.0, storey_height_m=3.2)),
    ("قاب ۱۳ طبقه، ۱۰۰ دهانه در راستای ۱۰۰۰ متری و ۲۰۰ دهانه در راستای ۲۰۰۰ متری",
     dict(storeys=13, bays_x=100, bays_y=200, bay_x_m=10.0, bay_y_m=10.0)),
    ("a 6 storey frame with 4 bays of 7 m in X and 2 bays of 6 m in Y, storey height 3.5 m",
     dict(storeys=6, bays_x=4, bays_y=2, bay_x_m=7.0, bay_y_m=6.0, storey_height_m=3.5)),
    ("6-story building, 3x4 bays, 5 m spans, floor height 3 m", dict(storeys=6, bays_x=3, bays_y=4, bay_x_m=5.0)),
    ("ساختمان هشت طبقه سه دهانه در سه دهانه با دهانه ۵ متر و ارتفاع ۳ متر",
     dict(storeys=8, bays_x=3, bays_y=3, bay_x_m=5.0, storey_height_m=3.0)),
    ("قاب ۷ طبقه ۵ دهنه ۴ متری در هر دو جهت", dict(storeys=7, bays_x=5, bays_y=5, bay_x_m=4.0, bay_y_m=4.0)),
    ("10 floors, 3 bays along 18 m and 2 bays along 12 m", dict(storeys=10, bays_x=3, bays_y=2, bay_x_m=6.0, bay_y_m=6.0)),
]


@pytest.mark.parametrize("text,expected", CASES)
def test_phrasing_variants(text, expected):
    got = inputs_from_texts([text])
    assert got is not None
    for k, v in expected.items():
        assert got[k] == pytest.approx(v), (k, got)


class _Conv:
    def __init__(self, projects):  # {pid: (runs, [texts])}
        self.p = projects

    def list_project_chat_runs(self, acc, pid):
        return self.p[str(pid)][0]

    def list_conversations(self, acc, project_id=None, limit=200):
        return [SimpleNamespace(id=str(project_id), project_id=project_id, title="c")]

    def list_messages(self, cid, acc):
        return [SimpleNamespace(role="user", content=t, created_at=f"2026-01-{i + 10:02d}") for i, t in enumerate(self.p[cid][1])]


def test_each_project_gets_its_own_values_and_only_missing_fields_are_assumed():
    a, b, c = str(uuid4()), str(uuid4()), str(uuid4())
    conv = _Conv({a: ([], [CASES[0][0]]), b: ([], ["ساختمان ۹ طبقه ۲ دهنه در ۴ دهنه"]), c: ([], ["سلام"])})
    ra, rb, rc = (resolve_project_frame(conv, None, p) for p in (a, b, c))
    assert ra["source"] == "chat_text" and ra["inputs"]["storeys"] == 5 and ra["assumed"] == []
    assert rb["inputs"]["storeys"] == 9 and (rb["inputs"]["bays_x"], rb["inputs"]["bays_y"]) == (2, 4)
    assert set(rb["assumed"]) == {"bay_x_m", "bay_y_m", "storey_height_m"} and len(rb["assumptions_fa"]) == 3
    assert rc["source"] == "default"


def test_run_missing_fields_filled_from_chat_before_defaults():
    p = str(uuid4())
    run = {"kind": "frame_optimization", "inputs": {"storeys": 4, "bays_x": 2, "bays_y": 2}, "created_at": "x"}
    conv = _Conv({p: ([run], ["قاب ۴ طبقه ۲ دهنه ۷ متری در هر دو جهت با ارتفاع طبقه ۳.۵ متر"])})
    r = resolve_project_frame(conv, None, p)
    assert r["inputs"]["bay_x_m"] == 7.0 and r["inputs"]["storey_height_m"] == 3.5 and r["assumed"] == []
