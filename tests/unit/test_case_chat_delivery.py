"""Тесты доставки единого чата: outbox, дедуп, уведомления."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfrfr.integrations.max.case_chat_log import append_client_case_message, reset_pending_for_tests
from sfrfr.services.case_chat_delivery import (
    CHAT_NOTIFY_NEUTRAL,
    find_message_by_external_id,
    mirror_client_message_to_max,
    notify_client_new_chat_message,
)


@patch("sfrfr.db.session.get_supabase_client")
def test_find_message_by_external_id(mock_sb: MagicMock) -> None:
    table = MagicMock()
    mock_sb.return_value.table.return_value = table
    chain = table.select.return_value.eq.return_value.limit.return_value.execute
    chain.return_value.data = [{"id": "m1", "case_id": "c1"}]
    row = find_message_by_external_id("ext-42")
    assert row is not None
    assert row["id"] == "m1"


@patch("sfrfr.services.case_chat_delivery.process_pending_outbox")
@patch("sfrfr.services.case_chat_delivery.enqueue_max_delivery")
def test_mirror_client_message_to_max(mock_enqueue: MagicMock, mock_process: MagicMock) -> None:
    case = {"id": "case-uuid", "clients": {"max_user_id": "max99"}}
    mirror_client_message_to_max(case, "Привет", message_id="msg1")
    mock_enqueue.assert_called_once()
    mock_process.assert_called_once_with(limit=5)


@patch("sfrfr.integrations.max.client.MaxBotClient")
def test_notify_client_neutral_no_pii(mock_bot_cls: MagicMock) -> None:
    bot = MagicMock()
    bot.available = True
    mock_bot_cls.return_value = bot
    notify_client_new_chat_message(case_id="c1", max_user_id="u1", preview_body="секретный текст")
    bot.send_message.assert_called_once_with(text=CHAT_NOTIFY_NEUTRAL, user_id="u1")


@patch("sfrfr.integrations.max.client.MaxBotClient")
def test_notify_skips_when_already_neutral(mock_bot_cls: MagicMock) -> None:
    notify_client_new_chat_message(
        case_id="c1",
        max_user_id="u1",
        preview_body=CHAT_NOTIFY_NEUTRAL,
    )
    mock_bot_cls.assert_not_called()


@patch("sfrfr.services.case_chat_delivery.find_message_by_external_id")
def test_append_client_dedup_external_id(mock_find: MagicMock) -> None:
    reset_pending_for_tests()
    mock_find.return_value = {"id": "existing"}
    with patch("sfrfr.integrations.max.case_chat_log._insert_case_message") as mock_insert:
        append_client_case_message(
            case_id="00000000-0000-4000-8000-000000000001",
            max_user_id="u1",
            text="повтор",
            external_message_id="ext-dup",
        )
        mock_insert.assert_not_called()
