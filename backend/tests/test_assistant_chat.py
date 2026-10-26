"""Assistant summarisers answer from deterministic frame3d payloads (no LLM) and defer to engines for new models."""
import pytest

from app.application import assistant_chat as ac
from app.application.frame3d_chat_analysis import build_frame3d_payload

SPEC = ("3-storey RC intermediate moment frame, 2x2 bays of 5 m, storey height 3.2 m, columns 40x40 cm, beams 30x45 cm, "
        "f'c=30 MPa, fy=400 MPa, Standard 2800, high hazard, soil II, design per Mabhas 9")


@pytest.fixture(scope="module")
def payload():
    return build_frame3d_payload(SPEC)


@pytest.mark.parametrize("agent", [a for a in ac.ASSISTANT_TYPES])
def test_every_assistant_replies_without_placeholders(agent, payload):
    for text in ("summarize", "خلاصه کن"):
        body, meta = ac.assistant_reply(agent, text, payload)
        assert body.strip() and "In setup" not in body and "Auto-provisioned" not in body
        assert meta["assistant"] == agent and meta["starters"]


def test_load_assessment_lists_combinations(payload):
    body, _ = ac.assistant_reply("LOAD_ASSESSMENT_AGENT", "combos", payload)
    assert "1.2D+1.6L" in body and "kN" in body


def test_analysis_reports_drift_and_no_pdelta(payload):
    body, _ = ac.assistant_reply("ANALYSIS_AGENT", "review", payload)
    assert "drift" in body.lower() and "P-Δ" in body


def test_persian_reply(payload):
    body, _ = ac.assistant_reply("SEISMIC_AGENT", "پارامترهای لرزه ای", payload)
    assert "استاندارد ۲۸۰۰" in body


def test_no_data_gives_guidance_with_starters():
    body, meta = ac.assistant_reply("ANALYSIS_AGENT", "review", None)
    assert "no analysis result" in body.lower() and meta["starters"]


def test_new_model_text_goes_to_engines_and_summary_text_does_not():
    assert ac.wants_engine(SPEC, has_attachments=False, prior_user_texts=[])
    assert ac.wants_engine("anything", has_attachments=True, prior_user_texts=[])
    assert not ac.wants_engine("summarize the load combinations", has_attachments=False, prior_user_texts=[])


def test_normalize():
    assert ac.normalize_assistant("analysis_agent") == "ANALYSIS_AGENT"
    assert ac.normalize_assistant("bogus") is None and ac.normalize_assistant(None) is None
