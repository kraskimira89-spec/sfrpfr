"""Сообщения portal: internal-фильтр и зеркалирование в MAX."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfrfr.api.routes.portal import _is_internal_staff_message, _mirror_client_message_to_max


def test_internal_staff_message_detected() -> None:
    row = {"author_kind": "staff", "body": "[[internal]] заметка"}
    assert _is_internal_staff_message(row) is True
    assert _is_internal_staff_message({"author_kind": "staff", "body": "видно клиенту"}) is False
    assert _is_internal_staff_message({"author_kind": "client", "body": "[[internal]] x"}) is False


@patch("sfrfr.integrations.max.client.MaxBotClient")
def test_mirror_client_message_to_max_sends_when_linked(mock_bot_cls: MagicMock) -> None:
    bot = MagicMock()
    bot.available = True
    mock_bot_cls.return_value = bot
    case = {"clients": {"max_user_id": "12345"}}
    _mirror_client_message_to_max(case, "Вопрос из кабинета")
    bot.send_message.assert_called_once_with(text="Вопрос из кабинета", user_id="12345")


@patch("sfrfr.integrations.max.client.MaxBotClient")
def test_mirror_client_message_skips_without_max_user(mock_bot_cls: MagicMock) -> None:
    _mirror_client_message_to_max({"clients": {}}, "текст")
    mock_bot_cls.assert_not_called()
