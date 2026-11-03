"""Chat «بهینه کن» runs the full section optimizer with project model resolution and auto defaults."""

from app.application.optimization_full import chat_run


def test_default_frame_when_nothing_known():
    out = chat_run.run_chat_optimization("بهینه کن", None, time_budget_s=3)
    assert out["kind"] == "optimization_full"
    assert out["status"] == "done", out
    r = out["result"]
    assert r["groups"] and r["cost"] > 0
    assert r["assumed_inputs"][0].startswith("منبع مدل:")
    assert out["source"] == "default"
    assert "بهینه‌سازی کامل مقاطع" in chat_run.optimization_full_markdown(out)


def test_frame_from_message_wins():
    out = chat_run.run_chat_optimization("قاب ۲ طبقه ۲ دهانه در ۲ دهانه ۵ متری را بهینه کن", None, time_budget_s=3)
    assert out["status"] == "done", out
    assert out["source"] == "message"


def test_prior_chat_frame_used():
    prior = {"storeys": 2, "bays_x": 2, "bays_y": 1, "bay_x_m": 4.0, "bay_y_m": 4.0, "storey_height_m": 3.0}
    out = chat_run.run_chat_optimization("بهینه کن", prior, time_budget_s=3)
    assert out["status"] == "done", out
    assert out["source"] == "frame"


def test_error_is_reported_not_raised(monkeypatch):
    def boom(*a, **k):
        raise KeyError("beams")

    monkeypatch.setattr("app.application.optimization_full.engine.optimize_model", boom)
    out = chat_run.run_chat_optimization("بهینه کن", None, time_budget_s=1)
    assert out["status"] == "error" and out["result"] is None and out["error"]
    assert "انجام نشد" in chat_run.optimization_full_markdown(out)
