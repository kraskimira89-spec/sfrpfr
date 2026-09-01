"""Автоответ бота в чате кабинета по контексту дела."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfrfr.services.case_chat_bot import (
    auto_reply_to_client_message,
    rule_based_reply,
    try_immediate_rule_reply,
)


def test_rule_result_with_empty_work_map() -> None:
    reply = rule_based_reply("Когда будет результат проверки?", {})
    assert reply is not None


def test_rule_result_when_docs_review() -> None:
    work = {
        "status_key": "docs_review",
        "status_label": "Документы на проверке",
        "now_need": "Сейчас от вас ничего не требуется",
        "sla_note": "Срок проверки комплекта: до 1 рабочего дня.",
    }
    reply = rule_based_reply("Когда будет результат проверки?", work)
    assert reply is not None
    assert "1 рабочего дня" in reply
    assert "Итог" in reply or "итог" in reply.lower()


def test_rule_result_when_ready() -> None:
    work = {"status_key": "result_ready", "status_label": "Результат готов", "now_need": ""}
    reply = rule_based_reply("Когда будет результат?", work)
    assert reply is not None
    assert "готов" in reply.lower()


def test_rule_which_document() -> None:
    work = {"status_key": "waiting_docs", "now_need": "Загрузить выписку ИЛС"}
    reply = rule_based_reply("Какой документ загрузить сейчас?", work)
    assert reply is not None
    assert "ИЛС" in reply
    assert "Мои документы" in reply


@patch("sfrfr.services.case_chat_bot._work_map_for_case")
@patch("sfrfr.integrations.max.case_chat_log.append_bot_case_message")
def test_auto_reply_uses_rules_without_llm(
    mock_append: MagicMock,
    mock_work: MagicMock,
) -> None:
    mock_work.return_value = {
        "status_key": "docs_review",
        "status_label": "Документы на проверке",
        "now_need": "Сейчас от вас ничего не требуется",
        "sla_note": "до 1 рабочего дня",
        "required_uploaded": 2,
        "required_total": 2,
    }
    mock_append.return_value = {"id": "bot-1", "author_kind": "system", "body": "ответ бота"}
    case = {"id": "00000000-0000-0000-0000-000000000099", "clients": {}}
    row = auto_reply_to_client_message(case=case, user_text="Когда будет результат проверки?")
    assert row == mock_append.return_value
    mock_append.assert_called_once()
    assert mock_append.call_args.kwargs["text"]


@patch("sfrfr.services.case_chat_bot._llm_reply")
@patch("sfrfr.services.case_chat_bot._work_map_for_case")
@patch("sfrfr.integrations.max.case_chat_log.append_bot_case_message")
def test_try_immediate_rule_reply_skips_llm(
    mock_append: MagicMock,
    mock_work: MagicMock,
    mock_llm: MagicMock,
) -> None:
    mock_work.return_value = {
        "status_key": "docs_review",
        "now_need": "",
        "sla_note": "до 1 рабочего дня",
    }
    mock_append.return_value = {"id": "bot-1", "author_kind": "system"}
    case = {"id": "00000000-0000-0000-0000-000000000099", "clients": {}}
    row = try_immediate_rule_reply(case=case, user_text="Когда будет результат проверки?")
    assert row == mock_append.return_value
    mock_llm.assert_not_called()


@patch("sfrfr.services.case_chat_bot._llm_reply")
@patch("sfrfr.services.case_chat_bot._work_map_for_case")
@patch("sfrfr.integrations.max.case_chat_log.append_bot_case_message")
def test_try_immediate_rule_reply_none_without_match(
    mock_append: MagicMock,
    mock_work: MagicMock,
    mock_llm: MagicMock,
) -> None:
    mock_work.return_value = {"status_key": "waiting_docs", "now_need": ""}
    case = {"id": "00000000-0000-0000-0000-000000000099", "clients": {}}
    assert try_immediate_rule_reply(case=case, user_text="Здравствуйте, подскажите по стажу") is None
    mock_llm.assert_not_called()
    mock_append.assert_not_called()

