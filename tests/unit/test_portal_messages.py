"""Сообщения portal: internal-фильтр и зеркалирование в MAX."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfrfr.services.case_message_text import strip_internal_staff_prefix
from sfrfr.api.routes.portal import _is_internal_staff_message, _mirror_client_message_to_max


def test_internal_staff_message_detected() -> None:
    row = {"author_kind": "staff", "body": "[[internal]] заметка"}
    assert _is_internal_staff_message(row) is True
    assert _is_internal_staff_message({"author_kind": "staff", "body": "видно клиенту"}) is False
    assert _is_internal_staff_message({"author_kind": "client", "body": "[[internal]] x"}) is False


@patch("sfrfr.services.case_chat_delivery.process_pending_outbox")
@patch("sfrfr.services.case_chat_delivery.enqueue_max_delivery")
def test_mirror_client_message_to_max_sends_when_linked(
    mock_enqueue: MagicMock,
    mock_process: MagicMock,
) -> None:
    case = {"id": "case-uuid", "clients": {"max_user_id": "12345"}}
    _mirror_client_message_to_max(case, "Вопрос из кабинета", message_id="m1")
    mock_enqueue.assert_called_once_with(
        case_id="case-uuid",
        message_id="m1",
        max_user_id="12345",
        body="Вопрос из кабинета",
    )
    mock_process.assert_not_called()


@patch("sfrfr.services.case_chat_delivery.enqueue_max_delivery")
def test_mirror_client_message_skips_without_max_user(mock_enqueue: MagicMock) -> None:
    _mirror_client_message_to_max({"clients": {}}, "текст")
    mock_enqueue.assert_not_called()
