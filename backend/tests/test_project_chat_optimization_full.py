"""Project-chat «بهینه کن» (orchestrator path) also runs the full optimizer with project model resolution."""
from types import SimpleNamespace

from app.application import conversation_service as cs
from app.application.optimization_full import chat_run


def _svc():
    s = cs.ConversationService.__new__(cs.ConversationService)
    s._file_registry = None
    s._file_ingestion = None
    return s


def _conv():
    return SimpleNamespace(project_id="11111111-1111-1111-1111-111111111111", id="c1")


def test_orchestrator_optimization_gets_full_card(monkeypatch):
    calls = {}

    def fake(text, prior, **kw):
        calls.update(text=text, prior=prior, **kw)
        return {"kind": "optimization_full", "status": "done", "error": None, "source": "frame",
                "source_fa": "قاب چت «X»", "result": {"feasible": True, "cost": 1000, "currency": "IRR",
                                                       "assumed_inputs": ["منبع مدل: قاب چت «X»"]}}

    monkeypatch.setattr(chat_run, "run_chat_optimization", fake)
    meta = {"engineering_results": {"kind": "frame_optimization", "status": "completed"}}
    out = _svc()._attach_full_optimization(_conv(), SimpleNamespace(account_id="a"), "بهینه کن", [], "quick", meta)
    full = meta["engineering_results"]["optimization_full"]
    assert full["status"] == "done" and full["source_fa"] == "قاب چت «X»"
    assert calls["project_id"] == "11111111-1111-1111-1111-111111111111" and calls["text"] == "بهینه کن"
    assert out.startswith("quick") and "بهینه‌سازی کامل مقاطع" in out and "منبع مدل" in out


def test_non_optimization_results_untouched(monkeypatch):
    monkeypatch.setattr(chat_run, "run_chat_optimization", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    meta = {"engineering_results": {"kind": "frame3d_analysis"}}
    assert _svc()._attach_full_optimization(_conv(), None, "x", [], "c", meta) == "c"
    assert "optimization_full" not in meta["engineering_results"]


def test_full_optimizer_failure_keeps_quick_result(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(chat_run, "run_chat_optimization", boom)
    meta = {"engineering_results": {"kind": "frame_optimization"}}
    assert _svc()._attach_full_optimization(_conv(), None, "بهینه کن", [], "quick", meta) == "quick"


def test_real_run_with_project_defaults(monkeypatch):
    """No model anywhere in the project -> default frame assumed and reported."""
    from app.application.optimization_full import model_resolver
    monkeypatch.setattr(model_resolver, "resolve_project_frame",
                        lambda conv, acc, pid, include_default=True: {
                            "source": "default", "inputs": None if not include_default else {
                                "storeys": 2, "bays_x": 2, "bays_y": 1, "bay_x_m": 4.0, "bay_y_m": 4.0, "storey_height_m": 3.0},
                            "label": {"fa": "قاب پیش‌فرض", "en": "default"}, "assumptions_fa": []})
    monkeypatch.setattr(chat_run, "CHAT_TIME_BUDGET_S", 3, raising=False)
    meta = {"engineering_results": {"kind": "frame_optimization"}}
    out = _svc()._attach_full_optimization(_conv(), SimpleNamespace(account_id="a"), "بهینه کن", [], "q", meta)
    full = meta["engineering_results"]["optimization_full"]
    assert full["status"] == "done", full
    assert full["result"]["assumed_inputs"][0].startswith("منبع مدل:")
    assert "منبع مدل" in out
