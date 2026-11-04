"""Free chat questions go to the LLM (not the empty 'project readiness' template); downloads are never blank."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.application import conversation_service as cs
from app.application.agent_intent_routing import resolve_agent_intent
from app.platform_helper.service import HelperReply


def test_free_question_has_no_engineering_intent():
    assert resolve_agent_intent("چرا چیزی در فایل دانلودی نوشته نشده").score == 0.0
    assert resolve_agent_intent("قاب ۵ طبقه ۳ دهانه را تحلیل کن").score > 0.0


def test_is_free_question_false_for_mode_hint():
    assert cs.ConversationService._is_free_question("چرا", "چرا", [], "analyze") is False
    assert cs.ConversationService._is_free_question("چرا چیزی در فایل دانلودی نوشته نشده",
                                                    "چرا چیزی در فایل دانلودی نوشته نشده", [], "auto") is True


def test_empty_completed_detection():
    assert cs._is_empty_completed("### نتیجه\nبا موفقیت تکمیل شد.", {"mode": "agent_execution"})
    assert not cs._is_empty_completed("با موفقیت تکمیل شد.", {"engineering_results": {"kind": "frame3d_analysis"}})
    assert not cs._is_empty_completed("Mmax = 120 kN·m", {})


class _FakeLLM:
    def __init__(self, configured=True):
        self.configured = configured


class _FakeSvc:
    def __init__(self, reply: HelperReply | None, configured=True):
        self.llm = _FakeLLM(configured)
        self.reply = reply
        self.calls = []

    def converse(self, message, history, **kw):
        self.calls.append((message, list(history), kw))
        return self.reply


def _self():
    return SimpleNamespace(_helper_context=lambda conv, acc: {"project_selected": "P3"})


def _hist():
    from app.domain.models.conversation import MessageRole
    return [SimpleNamespace(role=MessageRole.USER, content="قاب ۵ طبقه"),
            SimpleNamespace(role=MessageRole.ASSISTANT, content="تحلیل شد"),
            SimpleNamespace(role=MessageRole.USER, content="چرا چیزی در فایل دانلودی نوشته نشده")]


def test_free_question_uses_llm_with_history_and_context(monkeypatch):
    svc = _FakeSvc(HelperReply("متن نقشه به دلیل نبود فونت ...", "general_chat", provider="gemini", model="m"))
    monkeypatch.setattr("app.application.platform_helper_factory.get_helper_service", lambda: svc)
    text, md = cs.ConversationService._llm_free_answer(_self(), None, None, "چرا چیزی در فایل دانلودی نوشته نشده",
                                                       "چرا چیزی در فایل دانلودی نوشته نشده", _hist(), [], None)
    assert "فونت" in text and md["provider"] == "gemini" and md["mode"] == "general_chat"
    message, history, kw = svc.calls[0]
    assert history == [("user", "قاب ۵ طبقه"), ("assistant", "تحلیل شد")]
    assert kw["context"]["project_selected"] == "P3"


@pytest.mark.parametrize("svc", [_FakeSvc(HelperReply("x", "general_chat", provider="stub")),
                                 _FakeSvc(None, configured=False)])
def test_llm_failure_shows_real_error_and_fallback(monkeypatch, svc):
    monkeypatch.setattr("app.application.platform_helper_factory.get_helper_service", lambda: svc)
    text, md = cs.ConversationService._llm_free_answer(_self(), None, None, "چرا؟", "چرا؟", [], [], None)
    assert md["mode"] == "llm_error" and md["error"]
    assert "Gemini" in text and "تکمیل شد" not in text and len(text) > 80


def test_empty_download_problem():
    from app.application.results_package import empty_download_problem
    import pymupdf

    assert empty_download_problem("a.pdf", b"") == "0 bytes"
    blank = pymupdf.open(); blank.new_page()
    assert empty_download_problem("a.pdf", blank.tobytes()) == "PDF pages are blank"
    full = pymupdf.open(); full.new_page().insert_text((50, 50), "B12")
    assert empty_download_problem("a.pdf", full.tobytes()) == ""
    assert empty_download_problem("t.csv", b"  \n") == "blank text file"
    assert empty_download_problem("t.csv", b"a,b\n1,2\n") == ""


def test_fonts_registered_when_system_has_none():
    from ezdxf.fonts import fonts
    from app.application.autocad import pdf_fonts

    fonts.font_manager.clear()
    fonts.font_manager._match_cache.clear()
    pdf_fonts._ready = False
    assert pdf_fonts.ensure_fonts() is True
    assert type(fonts.make_font("DejaVuSans.ttf", 1.0)).__name__ != "MonospaceFont"
