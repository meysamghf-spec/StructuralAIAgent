"""Platform helper: provider fallback, streaming, webhook signing/retry, dedupe/redaction, intents, admin API, chat hook."""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app.platform_helper.config import load_settings
from app.platform_helper.intents import classify
from app.platform_helper.issues import (InMemoryIssueStore, IssueNotifier, IssueReport, IssueService, redact,
                                        sign_body, verify_signature)
from app.platform_helper.llm import LLMClient, LLMUnavailableError, ProviderConfig
from app.platform_helper.service import HelperService


def _cfg(name: str, key: str = "k") -> ProviderConfig:
    return ProviderConfig(name=name, base_url=f"https://{name}.test/v1", model="m", api_key=key)


def _ok(text: str = "hello") -> dict:
    return {"model": "m", "choices": [{"message": {"content": text}}]}


# ------------------------------------------------------------------ config ----------------------------------------
def test_auto_mode_without_keys_uses_keyless_pollinations_only() -> None:
    s = load_settings({})
    assert [p.name for p in s.providers] == ["pollinations"] and s.providers[0].keyless
    assert not load_settings({"LLM_KEYLESS_FALLBACK": "0"}).providers


def test_auto_mode_orders_keyed_providers_before_keyless() -> None:
    s = load_settings({"LLM_GROQ_API_KEY": "g", "LLM_GEMINI_API_KEY": "x"})
    assert [p.name for p in s.providers] == ["gemini", "groq", "pollinations"]


def test_generic_openai_compatible_env_is_primary() -> None:
    s = load_settings({"LLM_BASE_URL": "https://x.test/v1", "LLM_API_KEY": "k", "LLM_MODEL": "m2"})
    assert s.providers[0].name == "primary" and s.providers[0].model == "m2" and s.providers[-1].name == "pollinations"


def test_stub_mode_has_no_providers() -> None:
    assert not load_settings({"LLM_PROVIDER": "stub"}).providers


# --------------------------------------------------------------------- llm ----------------------------------------
def test_429_cools_down_provider_and_falls_back() -> None:
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.host)
        if req.url.host == "a.test":
            return httpx.Response(429, headers={"retry-after": "30"})
        return httpx.Response(200, json=_ok("from b"))

    t = [0.0]
    c = LLMClient([_cfg("a"), _cfg("b")], transport=httpx.MockTransport(handler), clock=lambda: t[0], sleep=lambda s: None)
    assert c.chat([{"role": "user", "content": "x"}]).text == "from b"
    assert c.status()[0]["cooling_down_s"] == 30
    calls.clear()
    assert c.chat([{"role": "user", "content": "x"}]).provider == "b"
    assert calls == ["b.test"]  # a is skipped while cooling down
    t[0] = 31
    c.chat([{"role": "user", "content": "x"}])
    assert calls[-2:] == ["a.test", "b.test"]


def test_all_providers_failing_raises_unavailable() -> None:
    c = LLMClient([_cfg("a")], transport=httpx.MockTransport(lambda r: httpx.Response(500)), sleep=lambda s: None)
    with pytest.raises(LLMUnavailableError):
        c.chat([{"role": "user", "content": "x"}])


def test_auth_error_does_not_retry_and_long_cooldown() -> None:
    n = {"c": 0}

    def handler(req):
        n["c"] += 1
        return httpx.Response(401)

    c = LLMClient([_cfg("a")], transport=httpx.MockTransport(handler), sleep=lambda s: None, retries=3)
    with pytest.raises(LLMUnavailableError):
        c.chat([{"role": "user", "content": "x"}])
    assert n["c"] == 1 and c.status()[0]["cooling_down_s"] >= 500


def test_streaming_yields_deltas_and_falls_back_before_first_token() -> None:
    def sse(*parts: str) -> bytes:
        lines = [f"data: {json.dumps({'choices': [{'delta': {'content': p}}]})}\n\n" for p in parts]
        return ("".join(lines) + "data: [DONE]\n\n").encode()

    def handler(req):
        if req.url.host == "a.test":
            return httpx.Response(503)
        return httpx.Response(200, content=sse("Sa", "lam", "!"), headers={"content-type": "text/event-stream"})

    c = LLMClient([_cfg("a"), _cfg("b")], transport=httpx.MockTransport(handler), sleep=lambda s: None)
    assert list(c.stream([{"role": "user", "content": "x"}])) == ["Sa", "lam", "!"]


# ------------------------------------------------------------ issues / webhook --------------------------------------
def test_redaction_removes_keys_tokens_and_emails() -> None:
    out = redact("token=abc123 key sk-AAAAAAAAAAAAAAAAAAAAAA mail me@x.com Bearer abcdefghijklmnop1234")
    assert "abc123" not in out and "sk-AAAA" not in out and "me@x.com" not in out and "abcdefghijklmnop1234" not in out


def test_dedupe_increments_occurrences_and_notifies_once() -> None:
    sent: list[httpx.Request] = []
    n = IssueNotifier("https://hook.test/in", "s3cret", 1, transport=httpx.MockTransport(lambda r: (sent.append(r), httpx.Response(200))[1]),
                      background=False)
    svc = IssueService(InMemoryIssueStore(), n)
    a, created_a = svc.report(IssueReport(title="Approve fails", page="approvals", error_text="409"))
    b, created_b = svc.report(IssueReport(title="Approve fails", page="approvals", error_text="409"))
    assert created_a and not created_b and a.id == b.id and b.occurrences == 2
    assert len(sent) == 1


def test_webhook_signature_headers_and_payload_schema() -> None:
    got: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        got["req"] = req
        return httpx.Response(204)

    n = IssueNotifier("https://hook.test/in", "s3cret", 1, transport=httpx.MockTransport(handler), background=False)
    svc = IssueService(InMemoryIssueStore(), n)
    svc.report(IssueReport(title="T", summary="S"))
    req = got["req"]
    body = req.content
    assert verify_signature("s3cret", req.headers["x-platform-timestamp"], body, req.headers["x-platform-signature"])
    assert not verify_signature("wrong", req.headers["x-platform-timestamp"], body, req.headers["x-platform-signature"])
    data = json.loads(body)
    assert data["schema_version"] == 1 and data["event"] == "platform_issue.created" and data["product"] == "structuralai"
    assert {"id", "title", "status", "severity", "proposed_fix", "dedupe_key"} <= set(data["issue"])
    assert req.headers["x-platform-event"] == "platform_issue.created"


def test_webhook_retries_on_5xx_then_succeeds_and_stops_on_4xx() -> None:
    codes = iter([500, 502, 200])
    sleeps: list[float] = []
    n = IssueNotifier("https://h.test", "", 3, transport=httpx.MockTransport(lambda r: httpx.Response(next(codes))),
                      sleep=sleeps.append, background=False)
    IssueService(InMemoryIssueStore(), n).report(IssueReport(title="x"))
    assert [d["result"] for d in n.deliveries] == [500, 502, 200] and len(sleeps) == 2
    n2 = IssueNotifier("https://h.test", "", 3, transport=httpx.MockTransport(lambda r: httpx.Response(400)), background=False)
    IssueService(InMemoryIssueStore(), n2).report(IssueReport(title="y"))
    assert len(n2.deliveries) == 1


def test_webhook_off_by_default() -> None:
    assert not IssueNotifier().enabled
    assert not load_settings({}).webhook_enabled


def test_post_back_validates_status_and_stores_draft_fix() -> None:
    svc = IssueService(InMemoryIssueStore())
    i, _ = svc.report(IssueReport(title="x"))
    with pytest.raises(ValueError):
        svc.post_back(i.id, status="bogus")
    u = svc.post_back(i.id, status="awaiting_approval", fix_note="PR #9", proposed_fix={"kind": "diff", "diff": "--- a"})
    assert u.status == "awaiting_approval" and u.proposed_fix["status"] == "draft"
    assert "PR #9" in u.user_status_message(False)


# ----------------------------------------------------------------- intents / service --------------------------------
@pytest.mark.parametrize("text,intent", [
    ("سلام", "greeting"), ("hello", "greeting"),
    ("گزارش مشکل: دکمه تایید کار نمی‌کند", "bug_report"),
    ("Approve button is not working", "bug_report"),
    ("وضعیت گزارش‌ها", "issue_status"),
    ("how do I run optimization?", "platform_help"),
    ("صفحه تایید پروژه چیست؟", "platform_help"),
    ("3D frame 4 stories 3x3 bays", "engineering"),
    ("simply supported beam 6 m uniform load 20 kN/m", "engineering"),
    ("Optimize the frame", "engineering"),
    ("تحلیل کن قاب سه بعدی ۴ طبقه", "engineering"),
    ("assume defaults", "engineering"),
])
def test_intent_classification(text: str, intent: str) -> None:
    assert classify(text).name == intent


def test_service_stub_without_llm_and_bug_report_flow() -> None:
    svc = HelperService(load_settings({"LLM_PROVIDER": "stub"}))
    r = svc.handle("hello")
    assert r and r.provider == "stub" and "assistant" in r.text.lower()
    assert svc.handle("3D frame 4 stories") is None  # engineering is never taken over
    rep = svc.handle("report a problem: approvals page 409", account_id="acc1")
    assert rep and rep.issue_id and "recorded" in rep.text
    st = svc.handle("issue status", account_id="acc1")
    assert st and "approvals page 409" in st.text


def test_service_uses_llm_with_knowledge_prompt_and_streams_tokens() -> None:
    seen: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        seen["system"] = body["messages"][0]["content"]
        chunks = "".join(f"data: {json.dumps({'choices': [{'delta': {'content': p}}]})}\n\n" for p in ("Use ", "Approvals"))
        return httpx.Response(200, content=(chunks + "data: [DONE]\n\n").encode())

    svc = HelperService(load_settings({"LLM_PROVIDER": "stub"}),
                        llm=LLMClient([_cfg("a")], transport=httpx.MockTransport(handler), sleep=lambda s: None))
    tokens: list[str] = []
    r = svc.handle("how do I approve a project?", on_token=tokens.append)
    assert r and r.text == "Use Approvals" and tokens == ["Use ", "Approvals"]
    assert "Never invent engineering numbers" in seen["system"] and "/workspace/approvals" in seen["system"]


def test_service_falls_back_to_stub_when_all_providers_down() -> None:
    svc = HelperService(load_settings({"LLM_PROVIDER": "stub"}),
                        llm=LLMClient([_cfg("a")], transport=httpx.MockTransport(lambda r: httpx.Response(500)), sleep=lambda s: None))
    r = svc.handle("سلام")
    assert r and r.provider == "stub"


# ------------------------------------------------------------------ API --------------------------------------------
def _register(api_client: TestClient) -> tuple[str, str]:
    email = f"ph-{uuid.uuid4().hex}@example.com"
    r = api_client.post("/api/v1/auth/register", json={"email": email, "password": "secure-password"})
    assert r.status_code == 201
    return r.json()["access_token"], email


def test_admin_api_auth_and_post_back_shows_in_chat(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("PLATFORM_ISSUE_ADMIN_TOKEN", "admin-token-123456789")
    from app.application import platform_helper_factory as f

    f.reset_helper_service(None)
    token, _ = _register(api_client)
    user = {"Authorization": f"Bearer {token}"}
    admin = {"Authorization": "Bearer admin-token-123456789"}

    # user reports a problem from chat
    chat = api_client.post("/api/v1/chat", json={"message": "گزارش مشکل: دکمه تایید 409 می‌دهد"}, headers=user)
    assert chat.status_code == 201, chat.text
    md = chat.json()["assistant_message"]["metadata"]
    assert md["intent"] == "bug_report" and md["issue_id"]
    issue_id = md["issue_id"]

    # authorization
    assert api_client.get("/api/v1/admin/platform-issues").status_code in (401, 403)
    assert api_client.get("/api/v1/admin/platform-issues", headers=user).status_code == 403
    r = api_client.get("/api/v1/admin/platform-issues?open_only=true", headers=admin)
    assert r.status_code == 200 and r.json()["count"] == 1 and r.json()["items"][0]["id"] == issue_id

    # machine token can propose a draft fix and post back, but cannot approve it
    r = api_client.post(f"/api/v1/admin/platform-issues/{issue_id}/propose-fix", headers=admin,
                        json={"kind": "pr_draft", "title": "Fix 409", "body": "details"})
    assert r.status_code == 200 and r.json()["status"] == "awaiting_approval" and r.json()["proposed_fix"]["status"] == "draft"
    assert api_client.post(f"/api/v1/admin/platform-issues/{issue_id}/approve-fix", headers=admin).status_code == 403
    r = api_client.post(f"/api/v1/admin/platform-issues/{issue_id}/post-back", headers=admin,
                        json={"status": "resolved", "fix_note": "PR #77 merged", "fix_pr_url": "https://github.com/x/y/pull/77"})
    assert r.status_code == 200
    assert api_client.post(f"/api/v1/admin/platform-issues/{issue_id}/post-back", headers=admin, json={"status": "nope"}).status_code == 422

    # the user sees it in chat and in /platform-issues/mine
    st = api_client.post("/api/v1/chat", json={"message": "وضعیت گزارش‌ها"}, headers=user)
    assert "PR #77" in st.json()["assistant_message"]["content"]
    mine = api_client.get("/api/v1/platform-issues/mine", headers=user).json()["items"]
    assert mine[0]["status"] == "resolved"


def test_admin_account_list_allows_human_admin(api_client: TestClient, monkeypatch) -> None:
    token, email = _register(api_client)
    monkeypatch.setenv("PLATFORM_ADMIN_ACCOUNTS", email)
    from app.application import platform_helper_factory as f

    f.reset_helper_service(None)
    h = {"Authorization": f"Bearer {token}"}
    assert api_client.get("/api/v1/admin/platform-issues", headers=h).status_code == 200


def test_chat_help_question_gets_stub_answer_without_llm(api_client: TestClient) -> None:
    token, _ = _register(api_client)
    r = api_client.post("/api/v1/chat", json={"message": "how do I optimize my frame?"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    assert r.json()["assistant_message"]["metadata"]["mode"] == "platform_helper"


def test_rename_conversation_and_streaming_tokens_event(api_client: TestClient) -> None:
    token, _ = _register(api_client)
    h = {"Authorization": f"Bearer {token}"}
    conv = api_client.post("/api/v1/conversations", json={"title": "New conversation"}, headers=h).json()
    cid = conv["id"]
    r = api_client.patch(f"/api/v1/conversations/{cid}", json={"title": "  Frame   study  "}, headers=h)
    assert r.status_code == 200 and r.json()["title"] == "Frame study"
    assert api_client.patch(f"/api/v1/conversations/{cid}", json={"title": ""}, headers=h).status_code == 422
    other, _ = _register(api_client)
    assert api_client.patch(f"/api/v1/conversations/{cid}", json={"title": "x"}, headers={"Authorization": f"Bearer {other}"}).status_code in (403, 404)

    # helper replies stream token events through /chat/stream, then the terminal event
    from app.application import platform_helper_factory as f

    def handler(req: httpx.Request) -> httpx.Response:
        chunks = "".join(f"data: {json.dumps({'choices': [{'delta': {'content': p}}]})}\n\n" for p in ("Hel", "lo"))
        return httpx.Response(200, content=(chunks + "data: [DONE]\n\n").encode())

    f.reset_helper_service(HelperService(load_settings({"LLM_PROVIDER": "stub"}),
                                         llm=LLMClient([_cfg("a")], transport=httpx.MockTransport(handler), sleep=lambda s: None)))
    with api_client.stream("POST", "/api/v1/chat/stream", json={"message": "hello", "conversation_id": cid}, headers=h) as resp:
        body = "".join(resp.iter_text())
    assert "event: agent_run.token" in body and '"delta": "Hel"' in body
    assert body.index("agent_run.token") < body.index("agent_run.completed")


def test_howto_with_leading_greeting_is_platform_help() -> None:
    from app.platform_helper import intents

    assert intents.classify("سلام، چطور بهینه‌سازی قاب را اجرا کنم؟").name == "platform_help"
    assert intents.classify("Hi, how do I optimize my frame?").name == "platform_help"
    assert intents.classify("Hi, explain what you can do.").name == "platform_help"
    assert intents.classify("run the analysis on my frame").name == "engineering"


def test_knowledge_does_not_claim_english_ltr_cards_are_intended() -> None:
    from app.platform_helper.prompt import load_knowledge

    text = load_knowledge()
    assert "Language and layout of chat cards" in text
    assert "is a BUG, never intended behaviour" in text
    assert "right-to-left" in text
