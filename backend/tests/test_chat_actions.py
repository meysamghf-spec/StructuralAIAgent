"""Chat-first commands: downloads, projects, assistants, approvals, plus contextual model edits (EN / FA / Finglish)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.application import chat_actions as ca
from app.application import frame3d_chat_analysis as f3
from app.application import frame3d_followup as fu


@pytest.mark.parametrize("text,name,zip_", [
    ("download the outputs", None, True),
    ("خروجی‌ها را دانلود کن", None, True),
    ("give me the ZIP of everything", None, True),
    ("دانلود همه فایل ها", None, True),
    ("فایل e2k بده", "e2k", False),
    ("خروجی ایتبس بده", "e2k", False),
    ("گزارش PDF بگیر", "report_pdf", False),
    ("DXF را دانلود کن", "dxf_plans", False),
    ("نقشه فونداسیون را بده", "dxf_foundation", False),
    ("excel tables please download", "all", False),
])
def test_parse_download(text, name, zip_):
    spec = ca.parse_download(text)
    assert spec is not None and spec["zip"] is zip_
    if name:
        assert spec["items"][0]["name"] == name


@pytest.mark.parametrize("text", ["3 storey RC frame, export to ETABS", "what is drift?", "show me the results", "Extract requirements from the specification PDF and summarize design parameters."])
def test_parse_download_ignores_other_requests(text):
    assert ca.parse_download(text) is None


def test_parse_project_assistant_approval():
    assert ca.parse_project_command("create a new project called Tower") == {"kind": "create", "name": "Tower"}
    assert ca.parse_project_command("یک پروژه جدید به نام برج بساز") == {"kind": "create", "name": "برج"}
    assert ca.parse_project_command("open project Tower") == {"kind": "open", "name": "Tower"}
    assert ca.parse_project_command("پروژه برج را باز کن") == {"kind": "open", "name": "برج"}
    assert ca.parse_project_command("show my projects") == {"kind": "list"}
    assert ca.parse_assistant_switch("switch to the seismic assistant") == "SEISMIC_AGENT"
    assert ca.parse_assistant_switch("دستیار بتن را انتخاب کن") == "CONCRETE_DESIGN_AGENT"
    assert ca.parse_assistant_switch("create an agent for bridges") is None
    assert ca.parse_approval_command("approve")["kind"] == "approve"
    assert ca.parse_approval_command("همه را تایید کن")["all"] is True
    assert ca.parse_approval_command("رد کن چون ارتفاع زیاد است")["kind"] == "reject"
    assert ca.parse_approval_command("show pending approvals")["kind"] == "list"


@pytest.mark.parametrize("text,key,value", [
    ("بتن را C30 کن", "fc_mpa", 30.0),
    ("concrete C35", "fc_mpa", 35.0),
    ("فولاد را ۴۰۰ بگیر", "fy_mpa", 400.0),
    ("column section 60x60", "column_b_m", 0.6),
    ("make it 6 storeys", "storeys", 6),
])
def test_model_edits_cover_materials_and_sections(text, key, value):
    assert fu.is_frame_followup(text) or fu.is_model_edit(text)
    edits = fu.model_edits(text)
    assert edits.get(key) == value, edits


@pytest.mark.parametrize("text", ["zone high", "soil type III", "زون زلزله را خیلی زیاد کن", "R=6"])
def test_param_edits_detected(text):
    assert fu.is_param_edit(text)


def test_report_pdf_is_real_pdf_and_in_package():
    from app.application import results_package as rp
    from app.application.report_pdf import markdown_to_pdf

    pdf = markdown_to_pdf("# گزارش\n\n- بتن C30\n- Drift OK", rtl=True)
    assert pdf[:4] == b"%PDF"
    inputs, _ = ca.default_frame_inputs()
    name, data, _mime = rp.item("report", "report_pdf", "pdf", inputs)
    assert data[:4] == b"%PDF"


def _token(client: TestClient) -> str:
    r = client.post("/api/v1/auth/register", json={"email": f"ca-{uuid.uuid4().hex}@example.com", "password": "secure-password", "display_name": "CA"})
    assert r.status_code == 201
    return r.json()["access_token"]


def _say(client, token, cid, text):
    r = client.post(f"/api/v1/conversations/{cid}/messages", json={"content": text}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code in (200, 201), r.text
    m = r.json()["assistant_message"]
    return m["content"], m.get("metadata") or {}


def test_chat_commands_end_to_end(api_client: TestClient):
    token = _token(api_client)
    h = {"Authorization": f"Bearer {token}"}
    cid = api_client.post("/api/v1/conversations", json={"title": "t"}, headers=h).json()["id"]

    _, meta = _say(api_client, token, cid, "download the outputs")  # no model yet -> defaults are stated, not invented silently
    d = meta["chat_downloads"]
    assert d["zip"] is True and d["assumed"] and d["inputs"]["storeys"]

    _, meta = _say(api_client, token, cid, "فایل e2k بده")
    assert meta["chat_downloads"]["items"][0]["name"] == "e2k"

    _, meta = _say(api_client, token, cid, "switch to the seismic assistant")
    assert meta["switch_assistant"] == "SEISMIC_AGENT"

    text, meta = _say(api_client, token, cid, "create a new project called Tower")
    assert meta["project_switch"]["name"] == "Tower" and "Tower" in text
    text, meta = _say(api_client, token, cid, "show my projects")
    assert "Tower" in text
    text, meta = _say(api_client, token, cid, "open project Tower")
    assert meta["project_switch"]["name"] == "Tower"
    text, meta = _say(api_client, token, cid, "show pending approvals")
    assert meta["intent"] == "approvals"
    # the real endpoints behind the buttons work for the inputs the chat returned
    body = {"inputs": d["inputs"], "kind": "model", "name": "e2k", "format": "e2k"}
    r = api_client.post("/api/v1/frame3d/download", json=body, headers=h)
    assert r.status_code == 200, r.text


def test_short_edits_route_to_frame_engine_only_with_a_model_in_context():
    from app.application.agent_intent_routing import frame_context, score_agent_intents
    from app.domain.models.agent import EngineeringAgentType

    for text in ("بتن را C30 کن", "column section 60x60", "زون زلزله را خیلی زیاد کن", "soil type III"):
        with frame_context(True):
            assert score_agent_intents(text)[0].agent_type == EngineeringAgentType.ANALYSIS_AGENT, text


def test_downloads_respect_the_plan_exports():
    from app.application import chat_actions as ca

    zip_spec = {"zip": True, "items": []}
    spec, withheld = ca.apply_plan(zip_spec, [])  # free plan: no model/DXF exports
    assert spec["zip"] is False and {i["name"] for i in spec["items"]} == {"all", "view3d", "report_pdf"} and withheld
    text, meta = ca.downloads_reply(spec, {"storeys": 3}, fa=True, withheld=withheld)
    assert "طرح" in text and meta["chat_downloads"]["zip"] is False
    assert all(not i["label"].isascii() for i in meta["chat_downloads"]["items"])

    spec, withheld = ca.apply_plan(zip_spec, ["e2k", "f2k", "s2k", "dxf"])
    assert spec["zip"] is True and not withheld
    spec, withheld = ca.apply_plan({"zip": False, "items": [
        {"kind": "model", "name": "e2k", "format": "e2k", "label": "ETABS model (.e2k)"},
        {"kind": "report", "name": "report_pdf", "format": "pdf", "label": "Calculation report (PDF)"}]}, [])
    assert [i["name"] for i in spec["items"]] == ["report_pdf"] and withheld == ["ETABS model (.e2k)"]
    assert ca.apply_plan(zip_spec, None) == (zip_spec, [])
    _, assumed = ca.default_frame_inputs(True)
    assert "طبقه" in assumed[0] and "storey" not in "".join(assumed)
