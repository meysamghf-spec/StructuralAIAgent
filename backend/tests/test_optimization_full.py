"""Full section optimizer (optimization_full): section-list parsing, model building, Mabhas 9 rebar, async jobs."""

import io
import time

from openpyxl import Workbook

from app.application import frame3d_chat_analysis as f3
from app.application.optimization_full import jobs
from app.application.optimization_full.builder import ensure_section, model_from_frame
from app.application.optimization_full.engine import Options, build_groups, optimize_model
from app.application.optimization_full.sections import extract_text, merge_lists, parse_section_lists

TEXT = ("ستون‌ها ۴۰x۴۰، ۴۰x۶۰، ۵۰x۵۰؛ تیرها 30x40, 30x50, 35x55\nمیلگرد ۱۶ و ۱۸ و ۲۰ AIII؛ بتن C30\n"
        "ستون‌های گوشه طبقات 1 تا 3: 50x50, 50x60\nbeams IPE200-IPE300, braces 2UNP120 BOX150x10\nsteel ST37")


def _frame(storeys=2, bays=1):
    return model_from_frame(f3.inputs_from_dict({"storeys": storeys, "bays_x": bays, "bays_y": bays, "bay_x_m": 5, "bay_y_m": 5}))


def test_parse_persian_lists():
    r = parse_section_lists(TEXT)
    assert [0.4, 0.6] in r["columns"] and [0.35, 0.55] in r["beams"]
    assert "IPE240" in r["beams"] and "2UNP120" in r["braces"] and "BOX150X10" in r["braces"]
    assert r["rebar_mm"] == [16, 18, 20]
    assert r["materials"] == {"fy_mpa": 400.0, "fc_mpa": 30.0, "steel_fy_mpa": 240.0}
    mt = r["member_types"][0]
    assert mt["type"] == "column" and mt["positions"] == ["corner"] and mt["storeys"] == [1, 2, 3]
    assert mt["candidates"] == [[0.5, 0.5], [0.5, 0.6]]


def test_parse_excel_and_merge():
    wb = Workbook(); ws = wb.active
    ws.append(["Columns"]); ws.append(["40x40"]); ws.append(["45x60"]); ws.append(["Beams"]); ws.append(["30x50"])
    buf = io.BytesIO(); wb.save(buf)
    r = parse_section_lists(extract_text("list.xlsx", buf.getvalue()))
    assert [0.45, 0.6] in r["columns"] and [0.3, 0.5] in r["beams"]
    m = merge_lists(r, {"rebar_mm": [18]})
    assert m["rebar_mm"] == [18] and [0.4, 0.4] in m["columns"]


def test_frame_model_tags_and_rect_sections():
    m = _frame(3, 2)
    cols = [x for x in m["members"] if x["type"] == "column"]
    assert {c["position"] for c in cols} == {"corner", "edge", "interior"}
    assert {b["direction"] for b in m["members"] if b["type"] == "beam"} == {"X", "Y"}
    name = ensure_section(m, "column", [0.4, 0.6])
    s = m["sections"][name]
    assert name == "C40X60" and abs(s["I33"] - 0.4 * 0.6**3 / 12) < 1e-12 and s["I22"] < s["I33"]


def test_member_type_rule_overrides_grouping():
    m = _frame(3, 2)
    lists = parse_section_lists("ستون‌های گوشه طبقات 1 تا 3: 50x50, 50x60")
    groups = build_groups(m, lists, Options(storey_band=3))
    corner = [g for g in groups if g["key"].startswith("rule")]
    assert len(corner) == 1 and len(corner[0]["members"]) == 12 and corner[0]["cands"] == [[0.5, 0.5], [0.5, 0.6]]


def test_optimize_rc_frame_real_rebar_design():
    r = optimize_model(_frame(2, 1), parse_section_lists("میلگرد 16 و 20 و 25"), {"time_budget_s": 30, "max_evals": 25})
    assert r["status"] == "done" and r["evaluations"] >= 2 and r["cost"] > 0
    assert r["settings"]["rebar_mm"] == [16, 20, 25]
    for g in r["groups"]:
        bars = g.get("bars") or g.get("top_bars") or ""
        assert "Φ" in bars and int(bars.split("Φ")[1]) in (16, 20, 25)
        assert g["DC"] >= 0
    assert r["quantities"]["rebar_kg"] > 0 and r["quantities"]["concrete_m3"] > 0
    if r["feasible"]:
        assert all(g["DC"] <= 1.0 for g in r["groups"]) and r["drift_ratio"] <= 1.0
    assert r["assumptions"]


def test_optimize_steel_members_from_catalog():
    m = _frame(2, 1)
    for mem in m["members"]:
        mem["section"] = ensure_section(m, mem["type"], "HEB240" if mem["type"] == "column" else "IPE300")
    r = optimize_model(m, parse_section_lists("تیرها IPE200 تا IPE400؛ ستون HEB160 تا HEB300"),
                       {"time_budget_s": 20, "max_evals": 15})
    assert r["groups"] and all(g["design"] == "AISC 360 H1-1" for g in r["groups"])
    assert r["quantities"]["steel_kg"] > 0
    assert all(g["section"].startswith(("IPE", "HEB")) for g in r["groups"])


def test_cancel_and_job_store(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "ROOT", tmp_path)
    m = _frame(2, 1)

    def work(progress, cancelled):
        return optimize_model(m, {}, {"time_budget_s": 60, "max_evals": 500}, progress=progress, cancelled=cancelled)

    job = jobs.start("u1", {}, work)
    time.sleep(1.0)
    assert jobs.cancel(job["id"])
    for _ in range(100):
        j = jobs.get(job["id"])
        if j["status"] in ("cancelled", "done", "error"):
            break
        time.sleep(0.2)
    assert j["status"] == "cancelled", j.get("error")
    assert jobs.get("../etc") is None


def test_api_parse_and_job(api_client, tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "ROOT", tmp_path)
    r = api_client.post("/api/v1/optimization-full/parse-sections", json={"text": TEXT})
    assert r.status_code == 200 and r.json()["lists"]["rebar_mm"] == [16, 18, 20]
    r = api_client.post("/api/v1/optimization-full/parse-sections-file",
                        files={"file": ("l.txt", "columns 40x40 50x50".encode(), "text/plain")})
    assert r.status_code == 200 and [0.5, 0.5] in r.json()["lists"]["columns"]
    r = api_client.post("/api/v1/optimization-full/jobs", json={
        "inputs": {"storeys": 2, "bays_x": 1, "bays_y": 1, "bay_x_m": 5, "bay_y_m": 5},
        "section_text": "میلگرد 18 و 22", "options": {"time_budget_s": 10, "max_evals": 8}})
    assert r.status_code == 200, r.text
    jid = r.json()["job"]["id"]
    for _ in range(200):
        j = api_client.get(f"/api/v1/optimization-full/jobs/{jid}").json()["job"]
        if j["status"] not in ("queued", "running"):
            break
        time.sleep(0.2)
    assert j["status"] == "done", j.get("error")
    assert j["result"]["settings"]["rebar_mm"] == [18, 22] and "owner" not in j
    assert api_client.get("/api/v1/optimization-full/jobs/deadbeef").status_code == 404


def test_routes_without_db(tmp_path, monkeypatch):
    """Route-level test with the auth dependency overridden (runs without PostgreSQL)."""
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.deps import get_conversation_service, get_current_account, get_project_access_service
    from app.api.routes import optimization_full as route
    from app.application.billing import service as billing

    monkeypatch.setattr(jobs, "ROOT", tmp_path)
    for fn in ("require_feature", "check_frame_size", "consume"):
        monkeypatch.setattr(billing, fn, lambda *a, **k: None)
    app = FastAPI(); app.include_router(route.router, prefix="/api/v1")
    app.dependency_overrides[get_current_account] = lambda: SimpleNamespace(account_id="t1")
    app.dependency_overrides[get_conversation_service] = lambda: None
    app.dependency_overrides[get_project_access_service] = lambda: None
    c = TestClient(app)
    r = c.post("/api/v1/optimization-full/parse-sections", json={"text": TEXT})
    assert r.status_code == 200 and r.json()["lists"]["rebar_mm"] == [16, 18, 20]
    r = c.post("/api/v1/optimization-full/parse-sections-file", files={"file": ("l.txt", b"columns 40x40 50x50", "text/plain")})
    assert r.status_code == 200 and [0.5, 0.5] in r.json()["lists"]["columns"]
    # no frame anywhere: the default frame is built and optimized automatically (assumptions listed in Persian)
    r = c.post("/api/v1/optimization-full/jobs", json={"options": {"time_budget_s": 5, "max_evals": 4}})
    assert r.status_code == 200, r.text
    did = r.json()["job"]["id"]
    for _ in range(200):
        j = c.get(f"/api/v1/optimization-full/jobs/{did}").json()["job"]
        if j["status"] not in ("queued", "running"):
            break
        time.sleep(0.2)
    assert j["status"] == "done", j
    assert any("پیش‌فرض" in a for a in j["result"]["assumed_inputs"])
    r = c.post("/api/v1/optimization-full/jobs", json={
        "inputs": {"storeys": 2, "bays_x": 1, "bays_y": 1, "bay_x_m": 5, "bay_y_m": 5},
        "section_text": "میلگرد 18 و 22", "options": {"time_budget_s": 10, "max_evals": 8}})
    assert r.status_code == 200, r.text
    jid = r.json()["job"]["id"]
    for _ in range(200):
        j = c.get(f"/api/v1/optimization-full/jobs/{jid}").json()["job"]
        if j["status"] not in ("queued", "running"):
            break
        time.sleep(0.2)
    assert j["status"] == "done", j.get("error")
    assert j["result"]["settings"]["rebar_mm"] == [18, 22] and "owner" not in j
    assert c.get("/api/v1/optimization-full/jobs/deadbeef").status_code == 404
    app.dependency_overrides[get_current_account] = lambda: SimpleNamespace(account_id="other")
    assert c.get(f"/api/v1/optimization-full/jobs/{jid}").status_code == 404  # other users cannot read it
