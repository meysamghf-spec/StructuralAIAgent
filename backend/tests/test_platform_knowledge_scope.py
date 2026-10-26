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


def test_error_report_is_diagnosed_not_filed_and_offers_a_report() -> None:
    assert classify("Approve button is not working").name == "diagnose"
    assert classify("اکسپورت ETABS خطا می‌دهد").name == "diagnose"
    assert classify("گزارش مشکل: دکمه تایید کار نمی‌کند").name == "bug_report"
    assert classify("report it").name == "report_it"
    assert classify("گزارش کن").name == "report_it"
    assert classify("بله، گزارش کن").name == "report_it"


def test_diagnose_faq_never_claims_to_change_code(fa: bool) -> None:
    msg = "approve button shows 409" if not fa else "دکمه تایید خطای 409 می‌دهد"
    ans = pk.answer_faq(msg, fa=fa, ctx=None, allow_overview=False)
    assert ans and ("409" in ans or "۴۰۹" in ans)
    assert ("نمی‌توانم کد یا سایت را تغییر دهم" in ans) if fa else ("cannot change code or fix the site" in ans)
    assert ("گزارش مشکل:" in ans) if fa else ("report a problem:" in ans)
    assert not re.search(r"(i (?:fixed|have fixed|will fix|changed)|اصلاح کردم|درست کردم)", ans, re.I)


def _svc() -> HelperService:
    return HelperService(load_settings({"LLM_PROVIDER": "stub"}), **knowledge_hooks())


def test_service_diagnoses_then_files_only_after_report_it() -> None:
    svc = _svc()
    r = svc.handle("Approve button is not working", account_id="a1")
    assert r and r.intent == "diagnose" and not r.issue_id
    assert "cannot change code" in r.text
    # no issue store wired in this unit test: "report it" with no prior error asks for a description
    r2 = svc.handle("report it", account_id="a1")
    assert r2 and r2.intent == "report_it" and not r2.issue_id


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
    assert "[pro]" not in sp  # per-question selection keeps billing out of this prompt
