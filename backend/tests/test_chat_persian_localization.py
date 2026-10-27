"""Persian conversations get Persian system cards (headings, steps, statuses, actions, errors); English is unchanged."""

import re
from uuid import uuid4

from app.application import chat_i18n
from app.application.conversation_service import _format_execution_response
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import (
    AgentExecutionRecord,
    AgentExecutionStatus,
    AgentResult,
    AgentValidationStatus,
)

_FA_REQUEST = "قاب ۳ طبقه را بهینه کن"
_LATIN_WORD = re.compile(r"[A-Za-z]{3,}")


def _record(user_request: str, ui_lang: str | None = None, **overrides) -> AgentExecutionRecord:
    parameters = {"conversation_id": str(uuid4())}
    if ui_lang:
        parameters["ui_lang"] = ui_lang
    defaults = dict(
        id=uuid4(),
        project_id=uuid4(),
        agent_definition_id=uuid4(),
        agent_version=1,
        execution_status=AgentExecutionStatus.COMPLETED,
        input_request={"user_request": user_request, "parameters": parameters},
        prompt_generation={"selected_agent_type": EngineeringAgentType.ANALYSIS_AGENT.value},
        agent_result=AgentResult(
            structured_output={"status": "completed"},
            generated_artifacts=[],
            recommendations=["Reply 'assume defaults' to auto-complete the missing steps."],
            validation_information={"warnings": ["Use DXF drawings when AutoCAD is not installed locally."]},
        ),
        validation_status=AgentValidationStatus.PASS,
    )
    defaults.update(overrides)
    return AgentExecutionRecord(**defaults)


def test_language_detection_ignores_follow_up_semicolon_and_empty_text() -> None:
    assert chat_i18n.detect_lang("سلام") == "fa"
    assert chat_i18n.detect_lang("hello") == "en"
    assert chat_i18n.detect_lang("   ") is None
    assert chat_i18n.detect_lang("a \u061b b") == "en"


def test_bare_follow_up_keeps_the_persian_conversation_language() -> None:
    assert chat_i18n.conversation_lang("3", [_FA_REQUEST]) == "fa"
    assert chat_i18n.conversation_lang("/workspace/model", [_FA_REQUEST]) == "fa"
    assert chat_i18n.conversation_lang("optimize the frame", [_FA_REQUEST]) == "en"
    assert chat_i18n.conversation_lang(_FA_REQUEST, ["hello there"]) == "fa"


def test_persian_cards_have_no_english_template_words() -> None:
    content, metadata = _format_execution_response(_record(_FA_REQUEST))
    assert "**وضعیت:** تکمیل شد" in content
    assert "### نتیجه" in content
    assert "### توصیه‌ها" in content
    assert "### هشدارها" in content
    assert "«پیش‌فرض‌ها را فرض کن»" in content
    for english in ("Status", "Recommendations", "Warnings", "Result"):
        assert english not in content
    assert metadata["lang"] == "fa"
    assert "درک درخواست" in [s["label"] for s in metadata["agent_run"]["steps"]]
    assert metadata["status_events"][0] == "ساخت زمینه‌ی مهندسی"
    assert "اعتبارسنجی نتایج" in metadata["status_events"]
    labels = [a["label"] for a in metadata["actions"]]
    assert "باز کردن دستیار تحلیل" in labels
    assert "مشاهده‌ی دستیارها" in labels
    assert not any(_LATIN_WORD.search(label) for label in labels)


def test_ui_lang_parameter_wins_over_the_text_of_a_bare_follow_up() -> None:
    content, metadata = _format_execution_response(_record("3", ui_lang="fa"))
    assert "**وضعیت:**" in content and metadata["lang"] == "fa"


def test_english_conversation_is_unchanged() -> None:
    content, metadata = _format_execution_response(_record("Analyze the model"))
    assert "**Status:** Completed" in content
    assert "### Recommendations" in content
    assert "### Warnings" in content
    assert "Reply 'assume defaults'" in content
    assert metadata["status_events"][0] == "Building engineering context"
    assert metadata["agent_run"]["steps"][0]["label"] == "Understanding request"
    assert "Open Analysis Agent" in [a["label"] for a in metadata["actions"]]
    assert metadata["lang"] == "en"


def test_failed_run_error_card_is_persian() -> None:
    record = _record(
        _FA_REQUEST,
        execution_status=AgentExecutionStatus.FAILED,
        error_metadata={"message": "Unsupported ETABS version"},
        agent_result=None,
        validation_status=AgentValidationStatus.ERROR,
    )
    content, metadata = _format_execution_response(record)
    assert "**وضعیت:** ناموفق" in content
    assert metadata["agent_run"]["error"]["title"] == "گردش‌کار مهندسی ناموفق بود"
    # unknown free-text reasons are never guessed at
    assert metadata["agent_run"]["error"]["reason"] == "Unsupported ETABS version"


def test_blocked_run_uses_persian_status_and_final_result() -> None:
    record = _record(
        _FA_REQUEST,
        execution_status=AgentExecutionStatus.BLOCKED,
    ) if hasattr(AgentExecutionStatus, "BLOCKED") else None
    if record is None:  # status enum without BLOCKED on this base
        return
    content, _ = _format_execution_response(record)
    assert "متوقف" in content


def test_pattern_translations_keep_numbers_and_unknown_text() -> None:
    assert chat_i18n.tr("3 relevant sections found", "fa") == "3 بخش مرتبط پیدا شد"
    assert chat_i18n.tr("2 members in model", "fa") == "2 عضو در مدل"
    assert chat_i18n.tr("Flexure PASS", "fa") == "خمش: قبول"
    assert chat_i18n.tr("Something unknown", "fa") == "Something unknown"
    assert chat_i18n.tr("Indexed", "en") == "Indexed"
    assert chat_i18n.tr(None, "fa") is None


def test_every_agent_type_has_a_persian_action_label() -> None:
    for agent in EngineeringAgentType:
        label = chat_i18n.tr(f"Open {agent.value.replace('_', ' ').title()}", "fa")
        assert label.startswith("باز کردن دستیار"), agent
        assert not _LATIN_WORD.search(label.replace("CAD", "")), (agent, label)


def test_localize_metadata_is_noop_for_english() -> None:
    meta = {"status_events": ["Validating results"], "actions": [{"label": "View Results", "href": "/x"}]}
    out = chat_i18n.localize_metadata(meta, "en")
    assert out["status_events"] == ["Validating results"]
    assert out["actions"][0]["label"] == "View Results"


def test_bare_path_followup_continues_persian_even_when_history_contains_the_current_message() -> None:
    from app.application.chat_i18n import conversation_lang

    # the stored history already holds the message being answered, newest first
    assert conversation_lang("/workspace/model", ["/workspace/model", "قاب را بهینه کن"]) == "fa"
    assert conversation_lang("12", ["12", "Optimize the frame"]) == "en"


def test_validation_status_detail_is_localized() -> None:
    from app.application.chat_i18n import tr

    assert tr("Validation: Warning", "fa") == "اعتبارسنجی: هشدار"
    assert tr("Validation: Warning", "en") == "Validation: Warning"
