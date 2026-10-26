"""The generated platform knowledge must cover every page, plan, export kind and payment fact, and the six audit questions
(how to export to ETABS / run optimization / what Validation-Approval-Memory are / billing + crypto / what it can't do /
how to download outputs) must be answered correctly with NO LLM (static FAQ) and routed away from the action regexes."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.application import chat_actions as ca
from app.application import platform_knowledge as pk
from app.application.billing import crypto, plans as bplans
from app.platform_helper.config import load_settings
from app.platform_helper.intents import classify, is_explain_question
from app.platform_helper.llm import LLMClient, ProviderConfig
from app.platform_helper.service import HelperService

NAV_TS = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "nav.ts"


@pytest.fixture(params=[True, False], ids=["fa", "en"])
def fa(request) -> bool:
    return request.param


# ---------------------------------------------------------------------------------------------- completeness
@pytest.mark.skipif(not NAV_TS.exists(), reason="frontend sources not present")
def test_every_nav_page_is_in_the_knowledge(fa: bool) -> None:
    hrefs = re.findall(r'href:\s*"([^"]+)"', NAV_TS.read_text(encoding="utf-8"))
    assert len(hrefs) >= 15
    known = {p[0] for p in pk.PAGES}
    missing = [h for h in hrefs if h not in known]
    assert not missing, f"pages missing from platform_knowledge.PAGES: {missing}"
    block = pk.build_platform_knowledge(fa)
    for h in hrefs:
        assert f"({h})" in block, h


def test_every_page_entry_is_a_real_nav_page() -> None:
    if not NAV_TS.exists():
        pytest.skip("frontend sources not present")
    hrefs = set(re.findall(r'href:\s*"([^"]+)"', NAV_TS.read_text(encoding="utf-8")))
    assert {p[0] for p in pk.PAGES} <= hrefs, "PAGES lists a page that is not in nav.ts"


def test_every_plan_limit_and_price_is_in_the_knowledge(fa: bool) -> None:
    block = pk.build_platform_knowledge(fa)
    cfg = bplans.load_config()
    for p in cfg["plans"]:
        assert f"[{p['id']}]" in block
        assert (p["name_fa"] if fa else p["name"]) in block
        assert str(p["price_usdt"]) in block.replace("۰", "0") or pk._fa_digits(p["price_usdt"]) in block
        for metric in ("projects", "analyses_per_month", "frame_max_storeys", "frame_max_bays", "storage_mb"):
            v = p["limits"][metric]
            assert pk._lim(v, fa) in block, (p["id"], metric)
    for d in cfg["durations"]:
        assert (d["label_fa"] if fa else d["label"]) in block


def test_every_export_kind_and_gate_is_in_the_knowledge(fa: bool) -> None:
    block = pk.build_platform_knowledge(fa)
    kinds = pk.export_kinds()
    assert {k["name"] for k in kinds} == {name for _p, _k, name, _f, _l in ca._SPECIFIC}
    for k in kinds:
        assert f"[{k['name']}]" in block
    by = {k["name"]: k for k in kinds}
    # plan gates come from the real gate function: models need their own name, drawings need "dxf", tables/figures/reports are open
    assert by["e2k"]["plans"] == ["pro", "office", "enterprise"] and by["dxf_plans"]["plans"] == by["e2k"]["plans"]
    assert by["all"]["plans"] == [p["id"] for p in bplans.load_config()["plans"]]
    for needle in ("ETABS", "SAFE", "SAP2000", "DXF", "PDF", "ZIP", "Excel" if not fa else "جدول"):
        assert needle in block, needle


def test_crypto_payment_facts_are_in_the_knowledge(fa: bool) -> None:
    block = pk.build_platform_knowledge(fa)
    for coin in {a.coin for a in crypto.ASSETS}:
        assert coin in block
    for std in {a.standard for a in crypto.ASSETS if a.standard != "native"}:
        assert std in block
    assert "BTCPay" in block and "USDT" in block
    assert pk._n(crypto.EXPIRY_MIN, fa) in block
    for pct in (10, 25):
        assert pk._n(pct, fa) in block
    assert ("فقط رمزارز" in block) if fa else ("crypto ONLY" in block)


def test_vam_assistants_and_limits_are_generated_from_code(fa: bool) -> None:
    from app.domain.models.human_approval import ApprovalStatus
    from app.domain.models.project_memory import MemoryType
    from app.domain.models.validation import ValidationStatus

    block = pk.build_platform_knowledge(fa)
    for enum in (ValidationStatus, ApprovalStatus, MemoryType):
        for m in enum:
            assert m.value in block, m
    from app.application.platform_assistants import PLATFORM_ASSISTANTS

    for name, _d, _c in PLATFORM_ASSISTANTS.values():
        assert name in block
    assert ("هرگز عدد مهندسی تولید نمی‌کند" in block) if fa else ("NEVER produces engineering numbers" in block)


def test_prompt_contains_rules_generated_block_and_user_context() -> None:
    svc = HelperService(load_settings({"LLM_PROVIDER": "stub"}), **_hooks())
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["system"] = json.loads(req.content)["messages"][0]["content"]
        return httpx.Response(200, json={"model": "m", "choices": [{"message": {"content": "ok"}}]})

    svc.llm = LLMClient([ProviderConfig(name="a", base_url="https://a.test/v1", model="m", api_key="k")],
                        transport=httpx.MockTransport(handler), sleep=lambda s: None)
    ctx = {"plan": "Free (رایگان)", "project_selected": "none", "model_exists": "no"}
    svc.converse("چطور خروجی ETABS بگیرم؟", context=ctx)
    sp = captured["system"]
    assert "Hard rules" in sp and "Generated platform facts" in sp and "ETABS" in sp and "capability matrix" in sp
    assert sp.index("Hard rules") < sp.index("Generated platform facts") < sp.index("Current session")
    assert "plan: Free" in sp and "model_exists: no" in sp
    assert "Reply in Persian" in sp


def test_user_context_has_plan_project_and_model() -> None:
    ctx = pk.user_context(None, project="Tower A", has_model=True)
    assert ctx["project_selected"] == "Tower A" and ctx["model_exists"] == "yes"
    assert pk.user_context(None)["project_selected"] == "none"


# ---------------------------------------------------------------------------------------------- routing: how-to beats action regexes
EXPLAIN = [
    "چطور خروجی ETABS بگیرم؟", "how do I export to ETABS", "how to download the outputs?", "چطور خروجی‌ها را دانلود کنم؟",
    "Validation چیست؟", "پرداخت کریپتو چطور کار می‌کند؟", "explain approvals", "what can't it do",
    "آیا امکان دریافت خروجی ETABS هست؟", "where can I download results", "how do I run optimization",
]
COMMANDS = [
    "خروجی‌ها را دانلود کن", "download the outputs", "download all outputs as zip", "خروجی ETABS را بده", "export ETABS",
    "can you download the outputs?", "میشه خروجی ETABS رو بدی؟", "آیا می‌توانید خروجی را بدهید؟", "show pending approvals",
    "simply supported beam 6 m uniform load 20 kN/m", "what is the max moment of a beam 6 m 20 kN/m",
    "قاب ۳ طبقه ۲×۲ دهانه ۵ متری را بهینه کن", "Optimize the frame",
]


@pytest.mark.parametrize("text", EXPLAIN)
def test_explain_questions_are_help_not_actions(text: str) -> None:
    assert is_explain_question(text)
    assert classify(text).name == "platform_help"


@pytest.mark.parametrize("text", ["What is structural drift?", "what is the difference between pinned and fixed supports?",
                                  "what is the effective length factor of a column"])
def test_general_engineering_questions_are_not_taken_over(text: str) -> None:
    assert classify(text).name == "engineering"


@pytest.mark.parametrize("text", COMMANDS)
def test_genuine_commands_are_not_explain_questions(text: str) -> None:
    assert not is_explain_question(text)
    assert classify(text).name == "engineering"


@pytest.mark.parametrize("text", ["خروجی‌ها را دانلود کن", "download the outputs", "خروجی ETABS را بده", "export ETABS"])
def test_commands_still_parse_as_downloads(text: str) -> None:
    assert ca.parse_download(text) is not None


# ---------------------------------------------------------------------------------------------- the six audit questions (no LLM)
def _faq(q: str) -> str:
    fa = any("\u0600" <= c <= "\u06ff" for c in q)
    out = pk.answer_faq(q, fa, {"plan_id": "free", "plan": "Free"}, allow_overview=True)
    assert out
    return out


def test_q1_how_to_export_to_etabs() -> None:
    a = _faq("چطور خروجی ETABS بگیرم؟")
    assert "ETABS" in a and "حرفه‌ای" in a and "خروجی ETABS را بده" in a and "رایگان" in a  # explanation + plan gate + offer
    e = _faq("how do I export to ETABS")
    assert "ETABS" in e and "Pro" in e and "export ETABS" in e


def test_q2_how_to_run_optimization() -> None:
    from app.application import optimization_checklist as oc

    a = _faq("چطور بهینه‌سازی را اجرا کنم؟")
    assert oc.EXAMPLE_COMMAND_FA in a and "بهینه‌سازی" in a and "بسته است" in a
    assert oc.EXAMPLE_COMMAND_EN in _faq("how to run optimization")


def test_q3_validation_approval_memory() -> None:
    a = _faq("Validation و Approval و Memory چی هستند؟")
    for needle in ("REQUIRES_ENGINEER_REVIEW", "PENDING", "DECISION", "CONVERSATION"):
        assert needle in a
    assert "everything is approved" not in a.lower()


def test_q4_billing_and_crypto() -> None:
    a = _faq("پرداخت کریپتو و ارتقای پلن چطور انجام می‌شود؟")
    for needle in ("فقط رمزارز", "USDT", "BTCPay", "۱۰", "۲۵", "/workspace/upgrades", "۳۰"):
        assert needle in a, needle


def test_q5_what_it_cannot_do() -> None:
    a = _faq("پلتفرم چه کارهایی را نمی‌تواند انجام دهد؟")
    assert "هرگز عدد مهندسی تولید نمی‌کند" in a and "رمزارزی" in a
    assert "NEVER produces engineering numbers" in _faq("what can't it do")


def test_q6_how_to_download_outputs() -> None:
    a = _faq("چطور خروجی‌ها را دانلود کنم؟")
    assert "ZIP" in a and "همه خروجی‌ها را دانلود کن" in a
    assert "download all outputs" in _faq("how do I download the outputs?")


def test_faq_never_overrides_free_chat_without_a_topic() -> None:
    assert pk.answer_faq("hello there", False, None, allow_overview=False) is None
    assert pk.answer_faq("hello there", False, None, allow_overview=True)  # overview only for platform questions


# ---------------------------------------------------------------------------------------------- service: FAQ replaces the generic stub
def _hooks() -> dict:
    from app.application.platform_helper_factory import knowledge_hooks

    return knowledge_hooks()


def test_service_down_returns_faq_not_generic_stub() -> None:
    svc = HelperService(load_settings({"LLM_PROVIDER": "stub"}),
                        llm=LLMClient([ProviderConfig(name="a", base_url="https://a.test/v1", model="m", api_key="k")],
                                      transport=httpx.MockTransport(lambda r: httpx.Response(500)), sleep=lambda s: None),
                        **_hooks())
    r = svc.handle("what can't it do", context={"plan_id": "pro"})
    assert r and r.provider == "faq" and "NEVER produces engineering numbers" in r.text
    r = svc.handle("how does billing and crypto payment work?")
    assert r and r.provider == "faq" and "crypto ONLY" in r.text
    g = svc.handle("hello")
    assert g and g.provider == "stub"  # greetings keep the friendly stub
    # free chat with no topic keeps the old fallback chain (provider "stub")
    assert svc.converse("tell a joke", intent="general_chat").provider == "stub"


def test_service_without_hooks_is_unchanged() -> None:
    svc = HelperService(load_settings({"LLM_PROVIDER": "stub"}))
    r = svc.handle("what can't it do")
    assert r and r.provider == "stub"


# ---------------------------------------------------------------------------------------------- provider pin
def test_pinned_provider_is_first_and_default_is_unchanged() -> None:
    base = {"LLM_PROVIDER": "auto", "LLM_GROQ_API_KEY": "g", "LLM_GEMINI_API_KEY": "m"}
    default = [p.name for p in load_settings(base).providers]
    pinned = load_settings({**base, "PLATFORM_HELP_LLM_PROVIDER": "gemini", "PLATFORM_HELP_LLM_MODEL": "gemini-pro-x"})
    assert [p.name for p in pinned.providers][0] == "gemini" and pinned.providers[0].model == "gemini-pro-x"
    assert sorted(p.name for p in pinned.providers) == sorted(default)
    assert [p.name for p in load_settings(base).providers] == default
    # pinned without its key is ignored; stub mode stays stub
    assert [p.name for p in load_settings({"LLM_PROVIDER": "auto", "PLATFORM_HELP_LLM_PROVIDER": "openai"}).providers] == ["pollinations"]
    assert load_settings({"LLM_PROVIDER": "stub", "PLATFORM_HELP_LLM_PROVIDER": "pollinations"}).providers == []


# ---------------------------------------------------------------------------------------------- end to end through the chat API
def _register(api_client: TestClient) -> dict:
    email = f"kb-{uuid.uuid4().hex}@example.com"
    r = api_client.post("/api/v1/auth/register", json={"email": email, "password": "secure-password"})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _chat(api_client: TestClient, h: dict, msg: str) -> dict:
    r = api_client.post("/api/v1/chat", json={"message": msg}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["assistant_message"]


def _down_service() -> HelperService:
    from app.application import platform_helper_factory as f

    svc = HelperService(load_settings({"LLM_PROVIDER": "stub"}),
                        llm=LLMClient([ProviderConfig(name="a", base_url="https://a.test/v1", model="m", api_key="k")],
                                      transport=httpx.MockTransport(lambda r: httpx.Response(500)), sleep=lambda s: None),
                        **f.knowledge_hooks())
    f.reset_helper_service(svc)
    return svc


@pytest.mark.parametrize("question,needles", [
    ("چطور خروجی ETABS بگیرم؟", ["ETABS", "خروجی ETABS را بده"]),
    ("how do I export to ETABS", ["ETABS", "export ETABS"]),
    ("how to run optimization", ["optimize a"]),
    ("Validation چیست؟", ["REQUIRES_ENGINEER_REVIEW"]),
    ("Approval چیست؟", ["PENDING"]),
    ("Memory چیست؟", ["DECISION"]),
    ("پرداخت کریپتو چطور کار می‌کند؟", ["USDT", "BTCPay"]),
    ("what can't it do", ["NEVER produces engineering numbers"]),
    ("چطور خروجی‌ها را دانلود کنم؟", ["ZIP"]),
    ("how do I download the outputs?", ["download all outputs"]),
])
def test_chat_api_audit_questions_answer_when_llm_is_down(api_client: TestClient, question: str, needles: list[str]) -> None:
    _down_service()
    h = _register(api_client)
    m = _chat(api_client, h, question)
    assert m["metadata"]["mode"] == "platform_helper" and m["metadata"]["provider"] == "faq", m["metadata"]
    for n in needles:
        assert n in m["content"], (question, n)
    assert "download" not in m["metadata"] and "downloads" not in m["metadata"]  # explained, not executed


def test_chat_api_commands_still_execute(api_client: TestClient) -> None:
    _down_service()
    h = _register(api_client)
    for cmd in ("خروجی‌ها را دانلود کن", "download the outputs"):
        m = _chat(api_client, h, cmd)
        assert m["metadata"].get("mode") != "platform_helper", cmd
        assert m["metadata"].get("intent") == "downloads" or "downloads" in json.dumps(m["metadata"]), (cmd, m["metadata"])


def test_chat_api_llm_reply_carries_user_context(api_client: TestClient) -> None:
    from app.application import platform_helper_factory as f

    seen: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["system"] = json.loads(req.content)["messages"][0]["content"]
        return httpx.Response(200, json={"model": "m", "choices": [{"message": {"content": "explained"}}]})

    f.reset_helper_service(HelperService(
        load_settings({"LLM_PROVIDER": "stub"}),
        llm=LLMClient([ProviderConfig(name="a", base_url="https://a.test/v1", model="m", api_key="k")],
                      transport=httpx.MockTransport(handler), sleep=lambda s: None), **f.knowledge_hooks()))
    h = _register(api_client)
    m = _chat(api_client, h, "how do I export to ETABS?")
    assert m["content"] == "explained"
    assert "plan: Free" in seen["system"] and "project_selected: none" in seen["system"] and "Generated platform facts" in seen["system"]


def test_api_error_report_is_diagnosed_then_filed_only_on_report_it(api_client: TestClient) -> None:
    _down_service()
    h = _register(api_client)
    r1 = api_client.post("/api/v1/chat", json={"message": "Approve button is not working, it shows 409"}, headers=h)
    assert r1.status_code == 201, r1.text
    md = r1.json()["assistant_message"]["metadata"]
    text = r1.json()["assistant_message"]["content"]
    assert md["intent"] == "diagnose" and not md.get("issue_id")
    assert "cannot change code" in text and "report a problem:" in text
    cid = r1.json()["assistant_message"]["conversation_id"]
    r2 = api_client.post("/api/v1/chat", json={"message": "report it", "conversation_id": cid}, headers=h)
    assert r2.status_code == 201, r2.text
    assert r2.json()["assistant_message"]["metadata"]["intent"] == "bug_report"
    assert r2.json()["assistant_message"]["metadata"]["issue_id"]
