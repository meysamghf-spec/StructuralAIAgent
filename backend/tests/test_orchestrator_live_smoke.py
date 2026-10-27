"""LOCAL ONLY: one real Gemini round trip through the whole chat. Skipped when the key file is absent (CI never has it).

The key is read from /home/box/secrets/gemini_api_key.txt into the process environment for this test only; it is never printed."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.application.orchestrator import engine
from app.application.orchestrator.llm import set_llm_for_tests
from tests.test_api_chat import _project, _register
from tests.test_chat_workflow_honesty import _chat

KEY_FILE = Path("/home/box/secrets/gemini_api_key.txt")

pytestmark = pytest.mark.skipif(not KEY_FILE.is_file(), reason="no local Gemini key file; live smoke test is local-only")


@pytest.fixture()
def live(monkeypatch):
    monkeypatch.setenv("LLM_GEMINI_API_KEY", KEY_FILE.read_text().strip())
    monkeypatch.setenv("PLATFORM_ORCHESTRATOR_MODE", "always")
    engine.reset_rate_limits()
    set_llm_for_tests(None)  # real client, built from the env above
    from app.application.orchestrator import llm as orch_llm

    orch_llm._llm = None
    yield
    orch_llm._llm = None


def test_real_gemini_builds_and_analyses_a_frame_in_persian(api_client: TestClient, live) -> None:
    token = _register(api_client)
    pid = _project(api_client, token)
    reply = _chat(api_client, token, pid, "یک قاب بتنی ۳ طبقه با ۲ دهانه در هر جهت (دهانه ۵ متر) بساز و تحلیل کن؛ نتیجه را مثل یک مهندس توضیح بده.")
    meta = reply["assistant_message"]["metadata"]
    text = reply["assistant_message"]["content"]
    if meta.get("mode") != "orchestrated":
        pytest.skip("Gemini was unavailable or rate limited (free tier); the rule-based fallback answered instead")
    assert [t["tool"] for t in meta["orchestrator"]["trace"]][:1] == ["analyze_frame"]
    assert meta["engineering_results"]["kind"] == "frame3d_analysis" and meta["engineering_results"]["status"] == "completed"
    assert any("\u0600" <= c <= "\u06ff" for c in text), "the reply to a Persian message must be Persian"
    assert meta["orchestrator"]["provider"] == "gemini" and meta["orchestrator"]["llm_calls"] >= 2
