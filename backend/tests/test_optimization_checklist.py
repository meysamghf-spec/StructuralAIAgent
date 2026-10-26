from app.application import frame_optimizer as fopt
from app.application import optimization_checklist as oc


def _report(**kw):
    base = {"model_summary": {"member_count": 0, "load_case_count": 0, "load_combination_count": 0, "section_count": 0},
            "findings": [], "code_configuration_valid": True, "usable_analysis_runs": 0, "available_analysis_runs": 0,
            "usable_design_runs": 0, "available_design_runs": 0}
    base.update(kw)
    return base


def test_empty_project_names_every_missing_step():
    c = oc.checklist_for_readiness(_report(), "p1")
    assert not c["ready"]
    assert {"model", "loads", "sections", "analysis"} <= set(c["missing_keys"])
    assert all(s["action"] for s in c["steps"] if not s["done"])
    assert c["auto_complete"]["assumptions"]["fa"]


def test_ready_project_has_no_missing_required_steps():
    c = oc.checklist_for_readiness(_report(
        model_summary={"member_count": 20, "load_case_count": 3, "load_combination_count": 5, "section_count": 4},
        usable_analysis_runs=1, available_analysis_runs=1))
    assert c["ready"] and c["missing_keys"] == []


def test_markdown_is_bilingual_and_offers_assume_defaults():
    c = oc.checklist_for_chat(has_frame=False)
    en = oc.checklist_markdown(c, "en")
    fa = oc.checklist_markdown(c, "fa")
    assert "assume defaults" in en and "❌" in en
    assert "پیش‌فرض" in fa and "مدل سازه" in fa


def test_optimize_without_frame_returns_checklist_not_vague_text():
    msg = fopt.missing_frame_checklist("optimize my building")
    assert "prerequisites" in msg and "Structural model" in msg


def test_assume_defaults_runs_optimization_and_lists_assumptions():
    res = fopt.build_optimization_from_chat("optimize the frame with default values", None,
                                            {"time_budget_s": 4, "max_evaluations": 8})
    assert res is not None
    assert "storeys" in res["assumed_defaults"]
    assert "Assumed defaults" in fopt.optimization_markdown(res, "en")


def test_assume_reply_after_checklist_continues_optimization():
    assert fopt.pending_optimize_text("optimize the frame", []) == "optimize the frame"
    merged = fopt.pending_optimize_text("farz kon", ["optimize the frame"])
    assert merged and "optimize" in merged
    assert fopt.pending_optimize_text("hello", ["optimize the frame"]) is None


def test_manual_run_and_optimize_accept_assume_defaults():
    from fastapi.testclient import TestClient

    import app.main as main
    from app.api.deps import get_current_account

    application = getattr(main, "app", None) or main.create_app()
    application.dependency_overrides[get_current_account] = lambda: object()
    try:
        client = TestClient(application)
        bad = client.post("/api/v1/frame3d/run", json={"inputs": {"storeys": 3}}).json()["frame3d_analysis"]
        assert bad["status"] == "MISSING_REQUIRED_INPUT" and bad["can_assume_defaults"]
        assert "assume defaults" in bad["message"]
        ok = client.post("/api/v1/frame3d/run", json={"inputs": {"storeys": 3}, "assume_defaults": True}).json()["frame3d_analysis"]
        assert ok["status"] == "completed" and "bays_x" in ok["assumed_defaults"]
        r = client.post("/api/v1/frame3d/optimize", json={"inputs": {}, "options": {"time_budget_s": 3, "max_evaluations": 6}})
        assert r.status_code == 422 and "assume_defaults" in r.text
        r2 = client.post("/api/v1/frame3d/optimize", json={"inputs": {}, "assume_defaults": True,
                                                              "options": {"time_budget_s": 3, "max_evaluations": 6}})
        assert r2.status_code == 200 and "storeys" in r2.json()["frame_optimization"]["assumed_defaults"]
    finally:
        application.dependency_overrides.clear()


def test_detailing_is_an_optional_step_right_after_design():
    from app.application import optimization_checklist as oc

    for chk in (oc.checklist_for_chat(has_frame=True),
                oc.checklist_for_readiness({"model_summary": {"member_count": 3}, "findings": []}, "p1")):
        keys = [s["key"] for s in chk["steps"]]
        assert keys[keys.index("design") + 1] == "detailing"
        det = chk["steps"][keys.index("detailing")]
        # honest: never claimed done, never blocks the optimization, offers the chat command in both languages
        assert det["done"] is False and det["optional"] is True
        assert "detailing" not in chk["missing_keys"]
        assert det["action"]["command"] == "detail the rebar" and det["action"]["command_fa"]
    assert "detail the rebar" in oc.checklist_markdown(oc.checklist_for_chat(has_frame=True), "en")
    assert "دیتیلینگ" in oc.checklist_markdown(oc.checklist_for_chat(has_frame=True), "fa")
