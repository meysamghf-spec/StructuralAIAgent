from types import SimpleNamespace
from datetime import datetime
from uuid import uuid4

from app.application.chat_runs import extract_runs, pick_usable_frame_run
from app.application.optimization_full.chat_run import frame_group_sections, optimized_frame3d, run_chat_optimization


def test_group_sections_take_largest_per_storey():
    gs = frame_group_sections([
        {"type": "column", "section": "C40X40", "storeys": [1, 2]},
        {"type": "column", "section": "C50X50", "storeys": [1]},
        {"type": "beam", "section": "B30X45", "storeys": [1, 2]},
        {"type": "beam", "section": "IPE300", "storeys": [3]},
    ])
    assert gs == {"C1": [0.5, 0.5], "C2": [0.4, 0.4], "B1": [0.3, 0.45], "B2": [0.3, 0.45]}


def test_chat_optimization_returns_reanalysed_optimized_frame_and_becomes_latest_frame():
    out = run_chat_optimization("قاب ۲ طبقه با ۲×۲ دهانه ۵ متری را بهینه کن", time_budget_s=3)
    assert out["status"] == "done"
    opt = out["optimized_frame3d"]
    assert opt["optimized"] is True and opt["inputs"]["group_sections"]
    assert out["original_inputs"]["storeys"] == 2 and not out["original_inputs"].get("group_sections")
    sections = {m["section"] for m in opt["viewer"]["members"]} if opt.get("viewer") else set()
    conv = SimpleNamespace(id=uuid4(), title="c")
    msg = SimpleNamespace(id=uuid4(), role="assistant", created_at=datetime(2026, 11, 3),
                          metadata={"engineering_results": {"kind": "frame_optimization", "optimization_full": out}})
    run = pick_usable_frame_run(extract_runs(conv, [msg]))
    assert run and run["optimized"] and run["inputs"]["group_sections"] == opt["inputs"]["group_sections"]
    assert sections is not None


def test_optimized_frame3d_none_without_rc_groups():
    assert optimized_frame3d({"storeys": 2}, {"groups": [{"type": "beam", "section": "IPE300", "storeys": [1]}]}) is None
