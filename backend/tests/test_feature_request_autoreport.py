"""Unsupported capability -> ETA + automatic feature request (flag-gated). Gemini is always mocked."""
from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.application import feature_requests as fr
from app.application import platform_helper_factory as factory
from app.infrastructure.repositories.postgres_platform_issue_repository import PostgresPlatformIssueRepository
from app.platform_helper.config import load_settings
from app.platform_helper.issues import IssueNotifier, IssueReport, InMemoryIssueStore
from app.platform_helper.llm import LLMUnavailableError
from app.platform_helper.service import HelperService
from tests.test_api_chat import _headers, _project, _register
from tests.test_chat_workflow_honesty import _chat

FA_TH = "تحلیل تاریخچه‌ی زمانی غیرخطی روی قاب انجام بده"
FA_PILE = "طراحی پی عمیق شمع برای ساختمان را انجام بده"
FINGLISH_TH = "lotfan tahlil tarikhche zamani gheyre khatti ro anjam bede"
EN_PUSH = "please run a pushover analysis on my frame"
SETTINGS = fr.FeatureRequestSettings(enabled=True)


class FakeGemini:
    configured = True

    def __init__(self, replies: list[Any] | None = None, default: dict | None = None) -> None:
        self.replies = list(replies or [])
        self.default = default
        self.calls: list[dict[str, Any]] = []

    def chat(self, messages, **opts):
        self.calls.append({"messages": messages, "opts": opts})
        item = self.replies.pop(0) if self.replies else self.default
        if isinstance(item, Exception):
            raise item
        if item is None:
            raise LLMUnavailableError("scripted outage")
        return SimpleNamespace(text=item if isinstance(item, str) else json.dumps(item))


def verdict(**kw) -> dict:
    return {"verdict": "unsupported", "capability_key": "wind_cfd_simulation", "title_en": "CFD wind simulation",
            "title_fa": "شبیه‌سازی CFD باد", "size": "medium", "alternative_id": "define_frame", "confidence": 0.9, **kw}


@pytest.fixture(autouse=True)
def _clean():
    fr.reset_state()
    fr.set_llm_for_tests(None)
    yield
    fr.reset_state()
    fr.set_llm_for_tests(None)
    factory.reset_helper_service(None)


def _svc(url: str = "", transport=None) -> HelperService:
    notifier = IssueNotifier(url, "s3cret", 1, transport=transport, sleep=lambda s: None, background=False) if url else None
    return HelperService(load_settings({"LLM_PROVIDER": "stub"}), store=InMemoryIssueStore(), notifier=notifier)


def run(text: str, svc: HelperService, account: str = "acc-1", history=None, settings=SETTINGS, ctx=None):
    return fr.handle_turn(text, history, account_id=account, project_id="p1", conversation_id="c1",
                          project_context=ctx, svc=svc, settings=settings)


# ------------------------------------------------------------------------------------------------ unit: detection
@pytest.mark.parametrize("text,key", [
    (FA_TH, "nonlinear_time_history_analysis"), (FINGLISH_TH, "nonlinear_time_history_analysis"),
    ("run a nonlinear time history analysis", "nonlinear_time_history_analysis"), (EN_PUSH, "pushover_analysis"),
    (FA_PILE, "pile_foundation"), ("tarahi paye omgh ro bokon", "pile_foundation"),
    ("design a retaining wall please", "retaining_wall_design"), ("طراحی اتصال گیردار فولادی", "steel_connection_design"),
])
def test_known_gap_matching(text: str, key: str) -> None:
    assert fr.match_known(text).key == key


@pytest.mark.parametrize("text", ["قاب ۵ طبقه بساز", "design a 3 storey frame", "تحلیل مودال انجام بده", "بدون پوش اور تحلیل کن",
                                  "run the analysis without nonlinear effects", "optimize the sections"])
def test_supported_or_negated_requests_are_not_known_gaps(text: str) -> None:
    assert fr.match_known(text) is None


def test_supported_request_never_triggers_even_with_model() -> None:
    llm = FakeGemini(default=verdict())
    fr.set_llm_for_tests(llm)
    svc = _svc()
    for text in ("یک قاب ۵ طبقه ۳ دهانه بساز و تحلیل کن", "analyze a 4 storey frame with 3 bays", "قاب را بهینه کن", "سلام",
                 "گزارش مشکل: دکمه کار نمی‌کند", "how do I optimize my frame?"):
        assert run(text, svc) is None, text
    assert llm.calls == [] and svc.store.list(limit=10) == []


def test_questions_do_not_trigger() -> None:
    svc = _svc()
    for text in ("what is pushover analysis?", "پوش‌اور چیست؟", "تفاوت تحلیل تاریخچه زمانی و طیفی چیست؟", "طراحی پی عمیق چطور انجام می‌شود؟"):
        assert run(text, svc) is None, text
    assert svc.store.list(limit=10) == []


def test_flag_off_does_nothing() -> None:
    svc = _svc()
    assert run(FA_TH, svc, settings=fr.FeatureRequestSettings(enabled=False)) is None
    assert svc.store.list(limit=10) == []
    assert fr.load_settings().enabled is False  # default


def test_model_detects_unknown_capability_and_picks_size() -> None:
    llm = FakeGemini(default=verdict())
    fr.set_llm_for_tests(llm)
    svc = _svc()
    out = run("please add a CFD wind simulation around my building", svc)
    assert out is not None
    text, meta = out
    assert "not available" in text and "1-2 days" in text and "not a commitment" in text and "automatically" in text
    assert "Closest thing" in text
    assert meta["intent"] == "feature_request" and meta["feature_request"]["size"] == "medium"
    [issue] = svc.store.list(limit=10)
    assert issue.category == "feature_request" and issue.kind == "feature_request"
    assert issue.details["capability_key"] == "cfd_simulation_wind"  # normalised (sorted)
    assert issue.details["estimate"]["source"] == "model"
    assert llm.calls[0]["opts"]["timeout"] == SETTINGS.llm_timeout_s
    assert "<user>" in llm.calls[0]["messages"][1]["content"]


def test_model_unclear_asks_clarifying_question_and_files_nothing() -> None:
    fr.set_llm_for_tests(FakeGemini(default={"verdict": "unclear", "clarifying_question": "Which model do you mean?", "confidence": 0.8}))
    svc = _svc()
    text, meta = run("please check the model against that thing", svc)
    assert text == "Which model do you mean?" and meta["intent"] == "feature_request_clarify"
    assert svc.store.list(limit=10) == []


def test_low_confidence_not_a_request_and_garbage_are_ignored() -> None:
    for reply in (verdict(confidence=0.3), verdict(verdict="not_a_request"), verdict(verdict="supported"), "not json at all"):
        fr.reset_state()
        fr.set_llm_for_tests(FakeGemini(default=reply if isinstance(reply, dict) else None, replies=[reply] if isinstance(reply, str) else []))
        svc = _svc()
        assert run("please add a CFD wind simulation around my building", svc) is None
        assert svc.store.list(limit=10) == []


def test_model_cannot_name_a_matrix_supported_capability_or_invent_an_alternative() -> None:
    fr.set_llm_for_tests(FakeGemini(default=verdict(capability_key="modal_analysis", alternative_id="made_up")))
    svc = _svc()
    assert run("please add a CFD wind simulation around my building", svc) is None
    fr.reset_state()
    fr.set_llm_for_tests(FakeGemini(default=verdict(alternative_id="made_up", size="weeks-and-weeks")))
    out = run("please add a CFD wind simulation around my building", svc, account="acc-2")
    text, meta = out
    assert meta["feature_request"]["alternative_id"] == "" and "Closest thing" not in text
    assert meta["feature_request"]["size"] == "large" and meta["feature_request"]["estimate_source"] == "rubric_fallback"  # invalid size -> rubric


# ------------------------------------------------------------------------------------------------ unit: message
def test_persian_message_has_estimate_not_promise_alternative_and_forwarding() -> None:
    svc = _svc()
    text, meta = run(FA_TH, svc)
    assert "هنوز در پلتفرم فعال نیست" in text
    assert "چند هفته" in text and "نه تعهد" in text and "بعد از بررسی و تأیید" in text
    assert "به‌طور خودکار" in text and "تیم توسعه" in text
    assert "نزدیک‌ترین کاری که همین حالا می‌شود" in text and "استاندارد ۲۸۰۰" in text
    assert "فردا" not in text and "حتماً" not in text
    assert meta["feature_request"]["size"] == "xlarge" and meta["feature_request"]["estimate_source"] == "rubric_fallback"


def test_finglish_gets_persian_message() -> None:
    text, _ = run(FINGLISH_TH, _svc())
    assert "هنوز در پلتفرم فعال نیست" in text


def test_english_message() -> None:
    text, meta = run(EN_PUSH, _svc())
    assert "Pushover analysis" in text and "weeks (about 2-6 weeks)" in text and "not a commitment" in text
    assert "review and approval" in text and "Closest thing that works right now" in text


def test_pile_is_large_with_alternative() -> None:
    text, meta = run(FA_PILE, _svc())
    assert "چند روز" in text and meta["feature_request"]["alternative_id"] == "define_frame"


def test_every_gap_alternative_is_a_real_example_id() -> None:
    ids = set(fr._alt_ids())
    for gap in fr._GAPS.values():
        assert gap.alt_id in ids and gap.size in fr.SIZES
        assert gap.matrix_id in {r[0] for r in fr._matrix_rows()}
        assert fr._matrix_status(gap.matrix_id) in ("no", "in_progress")


# ------------------------------------------------------------------------------------------------ unit: fallback
def test_model_down_still_informs_and_files_known_gap() -> None:
    fr.set_llm_for_tests(FakeGemini(default=None))  # raises LLMUnavailableError
    svc = _svc()
    text, meta = run(EN_PUSH, svc)
    assert "weeks" in text and meta["feature_request"]["estimate_source"] == "rubric_fallback"
    assert len(svc.store.list(limit=10)) == 1


def test_model_down_unknown_request_falls_through_to_normal_pipeline() -> None:
    fr.set_llm_for_tests(FakeGemini(default=None))
    svc = _svc()
    assert run("please add a CFD wind simulation around my building", svc) is None
    assert svc.store.list(limit=10) == []


def test_model_sizes_known_gap_and_caches_it() -> None:
    llm = FakeGemini(default={"verdict": "unsupported", "size": "large"})
    fr.set_llm_for_tests(llm)
    svc = _svc()
    _, m1 = run(FA_PILE, svc, account="a")
    _, m2 = run(FA_PILE, svc, account="b")
    assert m1["feature_request"]["estimate_source"] == "model" and m2["feature_request"]["size"] == "large"
    assert len(llm.calls) == 1  # cached per capability


def test_fallback_size_rubric() -> None:
    assert fr.fallback_size("nonlinear solver") == "xlarge" and fr.fallback_size("csv export of loads") == "small"
    assert fr.fallback_size("combination check") == "medium" and fr.fallback_size("something odd") == "large"


# ------------------------------------------------------------------------------------------------ unit: dedupe / rate limit
def test_dedupe_counter_and_per_user_repeat() -> None:
    svc = _svc()
    _, m1 = run(EN_PUSH, svc, account="u1")
    _, m2 = run("please run pushover analysis", svc, account="u2")
    _, m3 = run(EN_PUSH, svc, account="u1")
    assert (m1["feature_request"]["state"], m2["feature_request"]["state"], m3["feature_request"]["state"]) == ("filed", "counted", "repeat")
    [issue] = svc.store.list(limit=10)
    assert issue.occurrences == 2 and issue.details["request_count"] == 2 and len(issue.details["sample_requests"]) == 2
    text, _ = run("please run pushover analysis", svc, account="u2")
    assert "already" in text
    assert svc.store.list(limit=10)[0].occurrences == 2  # a repeat never inflates the counter


def test_counted_message_mentions_demand() -> None:
    svc = _svc()
    run(FA_TH, svc, account="u1")
    text, _ = run(FA_TH, svc, account="u2")
    assert "۲ درخواست" in text


def test_per_user_hourly_rate_limit() -> None:
    svc = _svc()
    s = fr.FeatureRequestSettings(enabled=True, max_new_per_hour=2)
    msgs = [EN_PUSH, FA_PILE, "design a retaining wall please", "run a nonlinear time history analysis"]
    states = [run(m, svc, account="u1", settings=s)[1]["feature_request"]["state"] for m in msgs]
    assert states == ["filed", "filed", "rate_limited", "rate_limited"]
    assert len(svc.store.list(limit=10)) == 2
    text, _ = run("design a retaining wall please", svc, account="u1", settings=s)
    assert "hourly limit" in text
    # another user is not affected
    assert run(msgs[3], svc, account="u2", settings=s)[1]["feature_request"]["state"] == "filed"


def test_model_call_budget_per_user() -> None:
    llm = FakeGemini(default={"verdict": "not_a_request"})
    fr.set_llm_for_tests(llm)
    svc = _svc()
    s = fr.FeatureRequestSettings(enabled=True, llm_max_per_hour=2)
    for i in range(5):
        run(f"please add a CFD wind simulation number {i} for my building", svc, settings=s)
    assert len(llm.calls) == 2


def test_store_failure_still_informs_user() -> None:
    class Boom(InMemoryIssueStore):
        def add(self, issue):
            raise RuntimeError("db down")

    svc = HelperService(load_settings({"LLM_PROVIDER": "stub"}), store=Boom())
    text, meta = run(EN_PUSH, svc)
    assert meta["feature_request"]["state"] == "store_failed" and "weeks" in text
    assert run(EN_PUSH, svc)[1]["feature_request"]["state"] == "store_failed"  # not marked as "seen" after a failure


# ------------------------------------------------------------------------------------------------ unit: privacy / payload
def test_request_is_redacted_before_storage_and_model() -> None:
    llm = FakeGemini(default=verdict())
    fr.set_llm_for_tests(llm)
    svc = _svc()
    msg = ("please add a CFD wind simulation, mail me at eng@firm.com phone 09121234567 api_key=sk-ABCDEFGHIJKLMNOP123456 "
           "national id 0012345678 see https://example.com/secret")
    run(msg, svc)
    [issue] = svc.store.list(limit=10)
    blob = json.dumps(issue.to_dict()) + json.dumps(llm.calls)
    for leak in ("eng@firm.com", "09121234567", "sk-ABCDEFGHIJKLMNOP123456", "0012345678", "example.com/secret"):
        assert leak not in blob, leak


def test_project_context_is_whitelisted() -> None:
    ctx = {"plan_id": "pro", "has_project": True, "has_model": True, "storeys": 5, "bays_x": 3, "project_name": "Secret Tower",
           "email": "a@b.com", "path": "/home/x", "note": "hello there"}
    assert fr.clean_project_context(ctx) == {"plan_id": "pro", "has_project": True, "has_model": True, "storeys": 5, "bays_x": 3}
    svc = _svc()
    run(EN_PUSH, svc, ctx=ctx)
    assert "Secret Tower" not in json.dumps(svc.store.list(limit=1)[0].to_dict())


def test_webhook_payload_schema_v1_with_optional_fields_and_milestone_update() -> None:
    sent: list[tuple[dict, httpx.Headers]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        sent.append((json.loads(req.content), req.headers))
        return httpx.Response(200)

    svc = _svc("https://hooks.example.test/x", httpx.MockTransport(handler))
    run(EN_PUSH, svc, account="u1", ctx={"plan_id": "free", "has_model": False})
    assert len(sent) == 1
    body, headers = sent[0]
    assert body["schema_version"] == 1 and body["event"] == "platform_issue.created"
    issue = body["issue"]
    for old in ("id", "title", "summary", "category", "severity", "status", "source", "occurrences", "created_at"):
        assert old in issue  # existing consumers keep working
    assert issue["kind"] == "feature_request" and issue["category"] == "feature_request"
    d = issue["details"]
    assert d["capability_key"] == "pushover_analysis" and d["estimate"]["size"] == "xlarge"
    assert d["estimate"]["hours_max"] == 1008 and d["closest_alternative"]["id"] == "define_frame"
    assert d["project_context"] == {"plan_id": "free", "has_model": False} and d["request_count"] == 1
    assert d["user_informed"] is True and d["sample_requests"] == [issue["user_message"]]
    assert "X-Platform-Signature" in headers and headers["X-Platform-Event"] == "platform_issue.created"
    # 2nd user: counted, no new "created"; 3rd distinct user reaches the milestone (3) -> platform_issue.updated
    run(EN_PUSH, svc, account="u2")
    assert len(sent) == 1
    run(EN_PUSH, svc, account="u3")
    assert [b["event"] for b, _ in sent] == ["platform_issue.created", "platform_issue.updated"]
    assert sent[1][0]["issue"]["details"]["request_count"] == 3 and sent[1][0]["issue"]["occurrences"] == 3


def test_bug_reports_keep_their_payload_shape() -> None:
    from app.platform_helper.issues import webhook_payload

    p = webhook_payload("platform_issue.created", IssueReport(title="t", summary="s", category="bug"), product="x")
    assert p["issue"]["kind"] == "bug" and p["issue"]["details"] == {} and p["schema_version"] == 1


def test_key_normalisation_is_stable() -> None:
    assert fr.normalize_capability_key("Wind_CFD_Simulations") == fr.normalize_capability_key("simulation cfd wind") == "cfd_simulation_wind"
    assert fr.normalize_capability_key("Pile Foundation Design") == "foundation_pile"


# ------------------------------------------------------------------------------------------------ e2e through /api/v1/chat
def _e2e_setup(api_client: TestClient, monkeypatch, llm=None, webhook=None):
    monkeypatch.setenv("FEATURE_REQUEST_AUTOREPORT_ENABLED", "true")
    monkeypatch.setenv("PLATFORM_ISSUE_ADMIN_TOKEN", "admin-token-123456789")
    notifier = None
    if webhook is not None:
        notifier = IssueNotifier("https://hooks.example.test/x", "s3cret", 1, transport=httpx.MockTransport(webhook),
                                 sleep=lambda s: None, background=False)
    factory.reset_helper_service(HelperService(load_settings({"LLM_PROVIDER": "stub", "PLATFORM_ISSUE_ADMIN_TOKEN": "admin-token-123456789"}), store=PostgresPlatformIssueRepository(),
                                               notifier=notifier, **factory.knowledge_hooks()))
    fr.set_llm_for_tests(llm)
    token = _register(api_client)
    return token, _project(api_client, token)


def test_e2e_persian_unsupported_request_filed_and_listed_for_admin(api_client: TestClient, monkeypatch) -> None:
    sent: list[dict] = []
    token, pid = _e2e_setup(api_client, monkeypatch, webhook=lambda r: (sent.append(json.loads(r.content)), httpx.Response(200))[1])
    reply = _chat(api_client, token, pid, "تحلیل تاریخچه‌ی زمانی غیرخطی انجام بده")
    msg = reply["assistant_message"]
    assert msg["metadata"]["intent"] == "feature_request" and "هنوز در پلتفرم فعال نیست" in msg["content"]
    assert "تخمین زمان" in msg["content"] and "نه تعهد" in msg["content"]
    issue_id = msg["metadata"]["feature_request"]["issue_id"]
    assert sent and sent[0]["issue"]["id"] == issue_id and sent[0]["issue"]["kind"] == "feature_request"

    admin = {"Authorization": "Bearer admin-token-123456789"}
    r = api_client.get("/api/v1/admin/platform-issues?kind=feature_request", headers=admin)
    assert r.status_code == 200 and r.json()["count"] == 1
    item = r.json()["items"][0]
    assert item["id"] == issue_id and item["kind"] == "feature_request" and item["details"]["estimate"]["size"] == "xlarge"
    assert api_client.get("/api/v1/admin/platform-issues?kind=bug", headers=admin).json()["count"] == 0
    assert api_client.get("/api/v1/admin/platform-issues?kind=nonsense", headers=admin).status_code == 422
    assert api_client.get("/api/v1/admin/platform-issues", headers=admin).json()["count"] == 1  # default list stays complete


def test_e2e_english_request_with_mocked_gemini_and_dedupe(api_client: TestClient, monkeypatch) -> None:
    llm = FakeGemini(default=verdict())
    token, pid = _e2e_setup(api_client, monkeypatch, llm=llm)
    text = "please add a CFD wind simulation around my building"
    first = _chat(api_client, token, pid, text)
    assert first["assistant_message"]["metadata"]["feature_request"]["state"] == "filed"
    assert "1-2 days" in first["assistant_message"]["content"]
    again = _chat(api_client, token, pid, text)
    assert again["assistant_message"]["metadata"]["feature_request"]["state"] == "repeat"
    admin = {"Authorization": "Bearer admin-token-123456789"}
    items = api_client.get("/api/v1/admin/platform-issues?kind=feature_request", headers=admin).json()["items"]
    assert len(items) == 1 and items[0]["occurrences"] == 1


def test_e2e_supported_requests_unchanged_and_nothing_filed(api_client: TestClient, monkeypatch) -> None:
    llm = FakeGemini(default=verdict())
    token, pid = _e2e_setup(api_client, monkeypatch, llm=llm)
    r = _chat(api_client, token, pid, "یک قاب ۳ طبقه ۲ دهانه بساز و تحلیل کن")
    assert r["assistant_message"]["metadata"].get("intent") != "feature_request"
    r = _chat(api_client, token, pid, "how do I optimize my frame?")
    assert r["assistant_message"]["metadata"]["mode"] == "platform_helper"
    assert llm.calls == []
    admin = {"Authorization": "Bearer admin-token-123456789"}
    assert api_client.get("/api/v1/admin/platform-issues?kind=feature_request", headers=admin).json()["count"] == 0


def test_e2e_flag_off_by_default(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.delenv("FEATURE_REQUEST_AUTOREPORT_ENABLED", raising=False)
    token = _register(api_client)
    pid = _project(api_client, token)
    r = _chat(api_client, token, pid, "تحلیل تاریخچه‌ی زمانی غیرخطی انجام بده")
    assert r["assistant_message"]["metadata"].get("intent") != "feature_request"


def test_postgres_repository_roundtrip_details_and_category_filter() -> None:
    repo = PostgresPlatformIssueRepository()
    tag = uuid.uuid4().hex
    fr_issue = repo.add(IssueReport(title=f"fr {tag}", summary="s", category="feature_request", dedupe_key=f"k{tag}",
                                    details={"capability_key": "x", "estimate": {"size": "small"}}))
    bug = repo.add(IssueReport(title=f"bug {tag}", summary="s", category="bug", dedupe_key=f"b{tag}"))
    got = repo.get(fr_issue.id)
    assert got.details["estimate"]["size"] == "small" and got.kind == "feature_request" and repo.get(bug.id).details == {}
    ids = {i.id for i in repo.list(category="feature_request", limit=500)}
    assert fr_issue.id in ids and bug.id not in ids
    repo.update(fr_issue.id, details={"capability_key": "x", "request_count": 2})
    assert repo.get(fr_issue.id).details["request_count"] == 2
    repo.delete(fr_issue.id), repo.delete(bug.id)
