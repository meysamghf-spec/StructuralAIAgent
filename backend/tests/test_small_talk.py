import pytest

from app.application import general_beam_engine as gbe
from app.application.conversation_service import ConversationService


@pytest.mark.parametrize("text", ["سلام", "سلام!", "سلاااام", "درود", "وقت بخیر", "hi", "Hello", "hey there", "Good morning"])
def test_greetings_detected(text):
    assert gbe.small_talk_kind(text) == "greeting"


@pytest.mark.parametrize("text", ["چطوری؟", "how are you", "سلام حالت چطوره", "تو کی هستی؟", "what can you do", "ممنون", "thanks", "خداحافظ"])
def test_other_small_talk_detected(text):
    assert gbe.small_talk_kind(text) is not None


@pytest.mark.parametrize("text", [
    "", "سلام تیر ساده با دهانه ۶ متر و بار ۲۰ کیلونیوتن بر متر را تحلیل کن",
    "hello, analyze a cantilever beam 3 m with point load 10 kN", "3D frame 3 stories", "نیروی برشی چیست؟",
])
def test_engineering_requests_are_not_small_talk(text):
    assert gbe.small_talk_reply(text) is None


def test_persian_greeting_reply_is_persian_saia_and_number_free():
    r = gbe.small_talk_reply("سلام")
    assert "SAIA" in r and "سلام" in r and "StructuralAIAgent" not in r
    assert "تیر" in r and "no AI language model" not in r


def test_english_greeting_reply_is_english():
    r = gbe.small_talk_reply("hi")
    assert r.startswith("Hello! I'm SAIA") and not any("\u0600" <= c <= "\u06ff" for c in r)


def test_fallback_message_language_and_name():
    fa, en = gbe.capabilities_message("یک سؤال آزاد"), gbe.capabilities_message("a free question")
    assert "SAIA" in fa and "SAIA" in en
    assert "no AI language model" not in fa + en
    assert "مبحث" in fa and not any("\u0600" <= c <= "\u06ff" for c in en)
    assert "SAIA" in gbe.CAPABILITIES_MESSAGE


def _service():
    return ConversationService.__new__(ConversationService)


@pytest.mark.parametrize("text,needle", [("سلام", "من SAIA هستم"), ("hi", "I'm SAIA")])
def test_general_chat_greets_without_any_llm(text, needle, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("LLM must not be used for a greeting")

    monkeypatch.setattr("app.application.platform_helper_factory.get_helper_service", boom)
    reply, meta = _service()._run_general_chat(text, [])
    assert needle in reply and meta["mode"] == "small_talk"


def test_general_chat_free_form_falls_back_in_user_language_when_llm_down(monkeypatch):
    class Down:
        class llm:  # noqa: N801
            configured = False

    class Gw:
        def complete(self, *_a, **_k):
            raise RuntimeError("down")

    monkeypatch.setattr("app.application.platform_helper_factory.get_helper_service", lambda: Down())
    svc = _service()
    svc._ai_gateway = Gw()
    reply, meta = svc._run_general_chat("نیروی برشی چیست؟", [])
    assert meta["mode"] == "capabilities" and "SAIA" in reply and "مبحث" in reply


def test_general_chat_beam_still_works_and_numbers_come_from_engine():
    reply, meta = _service()._run_general_chat("Analyze a simply supported beam with 6 m span and uniform load 20 kN/m", [])
    assert meta["engineering_results"]["results"]["max_moment_kn_m"] == 90.0
