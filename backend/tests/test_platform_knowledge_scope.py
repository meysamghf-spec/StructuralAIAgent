"""Scope tests for the generated platform knowledge: capability matrix, examples, login, what's new, diagnose, compactness."""
from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest

from app.application import platform_knowledge as pk
from app.application.platform_helper_factory import knowledge_hooks
from app.application.platform_whats_new import WHATS_NEW
from app.platform_helper.config import load_settings
from app.platform_helper.intents import classify
from app.platform_helper.llm import LLMClient, ProviderConfig
from app.platform_helper.service import HelperService

FRONT = Path(__file__).resolve().parents[2] / "frontend"


@pytest.fixture(params=[True, False], ids=["fa", "en"])
def fa(request) -> bool:
    return request.param


# ----------------------------------------------------------------------------------------- completeness
def test_capability_matrix_has_the_owner_stated_statuses(fa: bool) -> None:
    status = {i: k for i, _e, _f, k in pk.CAPABILITY_MATRIX}
    assert {status[i] for i in ("modal_analysis", "spectrum_2800", "equivalent_static", "mabhas9_concrete")} == {"yes"}
    assert {status[i] for i in ("p_delta", "response_spectrum_completion", "mabhas10_steel")} == {"in_progress"}
    assert {status[i] for i in ("time_history", "pushover", "nonlinear")} == {"no"}
    assert status["us_codes"] == "partial"
    assert {status[i] for i in ("export_e2k", "export_f2k", "export_s2k", "export_dxf")} == {"unconfirmed"}
    block = pk.build_platform_knowledge(fa)
    for i in status:
        assert f"[{i}]" in block, i


def test_every_example_and_login_option_and_public_page_is_in_the_knowledge(fa: bool) -> None:
    block = pk.build_platform_knowledge(fa)
    for row in pk.EXAMPLES:
        assert f"[{row[0]}]" in block
        assert (row[4] if fa else row[3]) in block
    for i, _e, _f in pk.LOGIN_OPTIONS:
        assert f"[{i}]" in block
    for href, _e, _f in pk.PUBLIC_PAGES:
        assert href in block
    assert "/traffic/" in block


def test_every_capability_has_an_example_command() -> None:
    ids = {r[0] for r in pk.EXAMPLES}
    assert {"edit_inputs", "run_task", "download_outputs", "optimization", "export_models", "assistant_switch"} <= ids


def test_slogan_matches_the_frontend() -> None:
    src = FRONT / "lib" / "legal-content.ts"
    if not src.exists():
        pytest.skip("frontend sources not present")
    assert pk.SLOGAN_EN in src.read_text(encoding="utf-8")


def test_public_pages_exist_in_the_frontend() -> None:
    if not (FRONT / "app").exists():
        pytest.skip("frontend sources not present")
    for href, _e, _f in pk.PUBLIC_PAGES:
        assert (FRONT / "app" / href.strip("/") / "page.tsx").exists(), href


# ----------------------------------------------------------------------------------------- what's new
def _ref_ids() -> set[str]:
    ids = {r[0] for r in pk.EXAMPLES} | {r[0] for r in pk.CAPABILITY_MATRIX} | {r[0] for r in pk.LOGIN_OPTIONS}
    ids |= {p[0] for p in pk.PAGES} | {p["id"] for p in pk.plan_rows()} | {r[0] for r in pk.DIAGNOSE}
    ids |= {k["name"] for k in pk.export_kinds()}
    return ids


def test_whats_new_refs_are_real_and_entries_are_injected(fa: bool) -> None:
    assert WHATS_NEW and len({w[1] for w in WHATS_NEW}) == len(WHATS_NEW)
    known = _ref_ids()
    block = pk.section_whats_new(fa, limit=len(WHATS_NEW))
    for month, eid, en, faq, refs in WHATS_NEW:
        assert re.fullmatch(r"\d{4}-\d{2}", month) and en and faq and refs
        assert f"[{eid}]" in block and (faq if fa else en) in block
        unknown = [r for r in refs if r not in known]
        assert not unknown, f"{eid}: unknown refs {unknown}"


def test_whats_new_is_in_every_prompt_block(fa: bool) -> None:
    for q in ("hello", "how do I export ETABS?", "چطور پرداخت کنم؟", "I get error 402"):
        assert "[assistant-knows-platform]" in pk.build_platform_knowledge(fa, q)


# ----------------------------------------------------------------------------------------- compactness
def test_per_question_blocks_are_compact_and_relevant() -> None:
    full = len(pk.build_platform_knowledge(False))
    billing = pk.build_platform_knowledge(False, "how do I pay with crypto?")
    assert len(billing) < full * 0.75
    assert "[pro]" in billing and "USDT" in billing and "[define_beam]" not in billing
    login = pk.build_platform_knowledge(False, "can I sign in with Google?")
    assert "[login_google]" in login and "[pro]" not in login
    for q in ("how do I pay with crypto?", "can I sign in with Google?", "what is Validation?"):
        assert "[time_history]" in pk.build_platform_knowledge(False, q)  # honest core is always present


def test_no_message_means_everything() -> None:
    assert set(pk.selected_sections(None)) == set(pk._SECTION_FN)


# ----------------------------------------------------------------------------------------- FAQ for new topics
@pytest.mark.parametrize("q,needle", [
    ("آیا time history پشتیبانی می‌شود؟", "time_history"),
    ("does it support pushover or nonlinear analysis?", "pushover"),
    ("آیا P-Delta دارد؟", "p_delta"),
    ("can I log in with Google?", "Google"),
    ("با گوگل وارد شوم؟", "گوگل"),
    ("what's new?", "assistant-knows-platform"),
    ("what commands can I type to change the inputs?", "edit_inputs"),
])
def test_faq_answers_new_topics(q: str, needle: str) -> None:
    ans = pk.answer_faq(q, fa=bool(re.search(r"[\u0600-\u06ff]", q)), ctx=None, allow_overview=False)
    assert ans and needle in ans, (q, ans)


# ----------------------------------------------------------------------------------------- diagnose
@pytest.mark.parametrize("msg,code", [
    ("I get QUOTA_EXCEEDED when I run analysis", "QUOTA_EXCEEDED"),
    ("the export gives error 402", "QUOTA_EXCEEDED"),
    ("approve button shows 409 conflict", "APPROVAL_409"),
    ("خطای REQUIRES_ANALYSIS می‌گیرم", "REQUIRES_ANALYSIS"),
    ("it says UNSUPPORTED_CODE", "UNSUPPORTED_CODE"),
])
def test_diagnose_rows_match_error_text(msg: str, code: str) -> None:
    assert code in {r[0] for r in pk.diagnose_matches(msg)}


def test_diagnose_table_is_complete_and_honest() -> None:
    codes = {r[0] for r in pk.DIAGNOSE}
    assert {"QUOTA_EXCEEDED", "RATE_LIMITED", "REQUIRES_ANALYSIS", "MISSING_REQUIRED_INPUT", "UNSUPPORTED_CODE", "APPROVAL_409", "EXPORT_LOCKED"} <= codes
    for fa_ in (True, False):
        block = pk.section_diagnose(fa_)
        assert ("نمی‌تواند کد را تغییر دهد" in block) if fa_ else ("CANNOT change code" in block)
        for c in codes:
            assert f"[{c}]" in block


def test_error_report_intents() -> None:
    assert classify("Approve button is not working").name == "diagnose"
    assert classify("اکسپورت ETABS خطا می‌دهد").name == "diagnose"
    assert classify("I get QUOTA_EXCEEDED").name == "diagnose"
    assert classify("the analysis returns 502 bad gateway").name == "diagnose"
    assert classify("گزارش مشکل: دکمه تایید کار نمی‌کند").name == "bug_report"
    assert classify("report it").name == "report_it"
    assert classify("گزارش کن").name == "report_it"
    assert classify("بله، گزارش کن").name == "report_it"


def test_diagnose_faq_never_claims_to_change_code(fa: bool) -> None:
    msg = "approve button shows 409" if not fa else "دکمه تایید خطای 409 می‌دهد"
    ans = pk.answer_faq(msg, fa=fa, ctx=None, allow_overview=False)
    assert ans and ("409" in ans or "۴۰۹" in ans)
    assert ("نمی‌توانم کد یا سایت را تغییر دهم" in ans) if fa else ("cannot change code or fix the site" in ans)
    assert ("خودکار برای مدیر پلتفرم گزارش می‌شوند" in ans) if fa else ("reported to the platform admin automatically" in ans)
    assert not re.search(r"(i (?:fixed|have fixed|will fix|changed)|اصلاح کردم|درست کردم)", ans, re.I)


def _svc(env: dict | None = None, clock=None, notifier=None) -> HelperService:
    return HelperService(load_settings({"LLM_PROVIDER": "stub", **(env or {})}), notifier=notifier, clock=clock, **knowledge_hooks())


def _issues(svc: HelperService) -> list:
    return svc.store.list(limit=100)


class _Clock:
    def __init__(self) -> None:
        self.t = 1_000_000.0

    def __call__(self) -> float:
        return self.t


def test_real_error_is_explained_and_auto_filed_with_context(fa: bool) -> None:
    svc = _svc()
    msg = "دکمه تایید خطای 409 می‌دهد، توکن=abcdef1234567890abcdef" if fa else "Approve button gives 409 conflict, token=abcdef1234567890abcdef"
    r = svc.handle(msg, account_id="acc1", project_id="p1", conversation_id="c1", page="approvals")
    assert r and r.intent == "diagnose" and r.issue_id
    assert ("این خطا خودکار گزارش شد" in r.text) if fa else ("reported automatically" in r.text)
    assert r.metadata["auto_report"] == "filed" and r.metadata["auto_reported"] and "APPROVAL_409" in r.metadata["error_codes"]
    assert ("cannot change code" in r.text) or ("نمی‌توانم کد یا سایت را تغییر دهم" in r.text)  # explained first
    (iss,) = _issues(svc)
    assert iss.source == "auto_detected" and iss.title.startswith("[APPROVAL_409]")
    assert iss.page == "approvals" and iss.project_id == "p1" and iss.conversation_id == "c1" and iss.account_id == "acc1"
    assert "abcdef1234567890abcdef" not in (iss.user_message + iss.error_text + iss.summary)  # redacted
    assert iss.locale == ("fa" if fa else "en")
    assert not re.search(r"(i (?:fixed|have fixed|changed)|اصلاح کردم|درست کردم)", r.text, re.I)


def test_notice_is_streamed_to_the_user() -> None:
    tokens: list[str] = []
    r = _svc().handle("Approve button gives 409 conflict", account_id="a", on_token=tokens.append)
    assert r and "reported automatically" in "".join(tokens) and r.text.endswith(tokens[-1])


def test_identical_report_inside_window_is_deduplicated_per_user() -> None:
    clock = _Clock()
    svc = _svc(clock=clock)
    r1 = svc.handle("Approve button gives 409 conflict", account_id="u1")
    r2 = svc.handle("approve button gives 409 conflict", account_id="u1")  # same error again
    assert r2.metadata["auto_report"] == "duplicate" and r2.issue_id == r1.issue_id
    assert "already reported automatically" in r2.text and len(_issues(svc)) == 1 and _issues(svc)[0].occurrences == 1
    # another user hitting the same error bumps the open issue's counter instead of creating a second one
    r3 = svc.handle("Approve button gives 409 conflict", account_id="u2")
    assert r3.metadata["auto_report"] == "filed" and len(_issues(svc)) == 1 and _issues(svc)[0].occurrences == 2
    # after the window the same user can report again (counter bumps)
    clock.t += 601
    r4 = svc.handle("Approve button gives 409 conflict", account_id="u1")
    assert r4.metadata["auto_report"] == "filed" and _issues(svc)[0].occurrences == 3


def test_per_user_rate_limit_is_honest() -> None:
    clock = _Clock()
    svc = _svc({"PLATFORM_ISSUE_AUTO_MAX_PER_HOUR": "2"}, clock=clock)
    outs = [svc.handle(f"the {w} page is not working", account_id="u1").metadata["auto_report"] for w in ("alpha", "beta", "gamma")]
    assert outs == ["filed", "filed", "rate_limited"]
    limited = svc.handle("the delta page is not working", account_id="u1")
    assert "reported automatically" not in limited.text and "خودکار گزارش شد" not in limited.text  # no false claim
    assert svc.handle("the alpha page is not working", account_id="u2").metadata["auto_report"] == "filed"  # other users unaffected
    clock.t += 3601
    assert svc.handle("the epsilon page is not working", account_id="u1").metadata["auto_report"] == "filed"
    assert len(_issues(svc)) == 3  # u2's "alpha" joined u1's open issue (occurrences) instead of duplicating it


@pytest.mark.parametrize("msg", [
    "I get QUOTA_EXCEEDED when I run another analysis",
    "I get error 402 on the free plan",
    "خطای QUOTA_EXCEEDED می‌گیرم",
    "RATE_LIMITED too many sign-in attempts",
])
def test_normal_plan_limits_are_explained_not_filed(msg: str) -> None:
    svc = _svc()
    r = svc.handle(msg, account_id="u1")
    assert r and r.intent == "diagnose" and r.metadata["auto_report"] == "expected_limit" and not r.issue_id
    assert not _issues(svc)
    assert ("normal plan limit" in r.text) or ("محدودیت عادی پلن" in r.text)
    assert "reported automatically" not in r.text and "خودکار گزارش شد" not in r.text
    # the user can still file it explicitly
    r2 = svc.handle("report it", [("user", msg), ("assistant", r.text)], account_id="u1")
    assert r2.issue_id and len(_issues(svc)) == 1


def test_quota_message_that_the_user_says_is_unexpected_is_filed() -> None:
    svc = _svc()
    r = svc.handle("I get QUOTA_EXCEEDED even though I already paid for Pro", account_id="u1")
    assert r.metadata["auto_report"] == "filed" and len(_issues(svc)) == 1


@pytest.mark.parametrize("msg,code", [
    ("I get REQUIRES_ANALYSIS when I export", "REQUIRES_ANALYSIS"),
    ("UNSUPPORTED_CODE error on my project", "UNSUPPORTED_CODE"),
    ("analysis returns 502 bad gateway", ""),
    ("the analysis timed out after 5 minutes", "SLOW_TIMEOUT"),
    ("Approve button is not working", ""),
    ("اکسپورت ETABS خطا می‌دهد", ""),
])
def test_other_real_errors_are_filed(msg: str, code: str) -> None:
    svc = _svc()
    r = svc.handle(msg, account_id="u1")
    assert r.metadata["auto_report"] == "filed" and r.issue_id, msg
    if code:
        assert code in r.metadata["error_codes"]
    assert _issues(svc)[0].severity in ("medium", "high")


def test_5xx_is_high_severity_and_timeout_is_performance() -> None:
    svc = _svc()
    svc.handle("analysis returns 502 bad gateway", account_id="u1")
    svc.handle("the analysis timed out after 5 minutes", account_id="u1")
    by = {i.title.split("]")[0]: i for i in _issues(svc)}
    assert any(i.severity == "high" for i in _issues(svc)) and any(i.category == "performance" for i in by.values())


@pytest.mark.parametrize("msg", ["What does UNSUPPORTED_CODE mean?", "REQUIRES_ANALYSIS چیست؟", "what is the 409 conflict error?"])
def test_pure_what_does_it_mean_questions_are_not_filed(msg: str) -> None:
    svc = _svc()
    r = svc.handle(msg, account_id="u1")
    assert r and not r.issue_id and not _issues(svc)


def test_auto_report_can_be_switched_off_and_manual_still_works() -> None:
    svc = _svc({"PLATFORM_ISSUE_AUTO_REPORT": "0"})
    r = svc.handle("Approve button is not working", account_id="u1")
    assert r.metadata["auto_report"] == "disabled" and not _issues(svc) and "report it" in r.text
    assert svc.handle("report it", [("user", "Approve button is not working"), ("assistant", r.text)], account_id="u1").issue_id


def test_report_it_after_an_auto_report_says_already_reported() -> None:
    svc = _svc()
    r = svc.handle("Approve button is not working", account_id="u1")
    r2 = svc.handle("report it", [("user", "Approve button is not working"), ("assistant", r.text)], account_id="u1")
    assert "already reported automatically" in r2.text and len(_issues(svc)) == 1 and _issues(svc)[0].occurrences == 1


def test_explicit_prefix_still_files_directly() -> None:
    svc = _svc()
    r = svc.handle("report a problem: the chart is blank", account_id="u1")
    assert r.intent == "bug_report" and r.issue_id and _issues(svc)[0].source == "user_report"


def test_auto_filed_issue_is_sent_through_the_signed_webhook_only_when_configured() -> None:
    import json as _json

    from app.platform_helper.issues import IssueNotifier, verify_signature

    sent: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        sent.append(req)
        return httpx.Response(200)

    hook = IssueNotifier("https://hook.test/in", "s3cret", 1, transport=httpx.MockTransport(handler), background=False)
    svc = _svc(notifier=hook)
    svc.handle("Approve button gives 409 conflict", account_id="u1", page="approvals")
    assert len(sent) == 1
    body = _json.loads(sent[0].content)
    assert body["schema_version"] == 1 and body["event"] == "platform_issue.created"
    assert body["issue"]["source"] == "auto_detected" and "APPROVAL_409" in body["issue"]["title"] and body["issue"]["page"] == "approvals"
    hdrs = {k.lower(): v for k, v in sent[0].headers.items()}
    sig = next(v for k, v in hdrs.items() if "signature" in k)
    ts = next(v for k, v in hdrs.items() if "timestamp" in k)
    assert verify_signature("s3cret", ts, sent[0].content, sig)
    off = _svc()  # default: stored in the DB/store only, no outbound call
    assert not off.notifier.enabled and off.handle("Approve button gives 409 conflict", account_id="u1").issue_id


def test_engine_failure_hook_files_once_and_never_raises() -> None:
    svc = _svc()
    a = svc.auto_report("Unexpected engine failure: ValueError", error_text="ValueError: boom password=hunter2", account_id="u1",
                        severity="high", codes=("ENGINE_FAILURE", "ValueError"))
    b = svc.auto_report("Unexpected engine failure: ValueError", error_text="ValueError: boom password=hunter2", account_id="u1",
                        severity="high", codes=("ENGINE_FAILURE", "ValueError"))
    assert a and b and a.id == b.id and len(_issues(svc)) == 1 and "hunter2" not in _issues(svc)[0].error_text


def test_prompt_for_an_error_report_carries_the_diagnose_rules() -> None:
    seen: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        import json
        seen["system"] = json.loads(req.content)["messages"][0]["content"]
        return httpx.Response(200, json={"model": "m", "choices": [{"message": {"content": "ok"}}]})

    svc = _svc()
    svc.llm = LLMClient([ProviderConfig(name="a", base_url="https://a.test/v1", model="m", api_key="k")],
                        transport=httpx.MockTransport(handler), sleep=lambda s: None)
    svc.converse("Approve button is not working, error 409")
    sp = seen["system"]
    assert "[APPROVAL_409]" in sp and "CANNOT change code" in sp and "Honest capability matrix" in sp
    assert "reported automatically" in sp and "do not ask the user to report it" in sp
    assert "[pro]" not in sp  # per-question selection keeps billing out of this prompt


def test_report_engine_failure_files_once_and_never_raises() -> None:
    from app.application import platform_helper_factory as f

    svc = _svc()
    f.reset_helper_service(svc)
    try:
        raise RuntimeError("boom token=abcdef1234567890abcdef")
    except RuntimeError as exc:
        a = f.report_engine_failure(exc, account_id="u1", conversation_id="c1", user_message="analyze my frame")
        b = f.report_engine_failure(exc, account_id="u1", conversation_id="c1", user_message="analyze my frame")
    assert a and a == b and len(_issues(svc)) == 1
    iss = _issues(svc)[0]
    assert iss.source == "auto_detected" and "abcdef1234567890abcdef" not in iss.error_text
    f.reset_helper_service(None)
