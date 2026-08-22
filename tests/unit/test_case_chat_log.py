"""Тесты ленты переписки MAX → case_messages."""

from __future__ import annotations

from pathlib import Path

from sfrfr.integrations.max.case_chat_log import (
    append_bot_case_message,
    append_client_case_message,
    flush_pending_case_chat,
    format_button_press,
    format_document_event,
    label_for_callback,
    reset_pending_for_tests,
)


def test_label_for_callback_human() -> None:
    assert label_for_callback("intake:whom:self") == "За себя"
    assert "Нажал кнопку: За себя" == format_button_press("intake:whom:self")
    assert label_for_callback("llmsoft:1:Нужна помощь") == "Нужна помощь"


def test_format_document_event() -> None:
    assert format_document_event(filename="ils.pdf", doc_type="ils") == "[Документ] ils.pdf · ils"


def test_pending_buffer_flush() -> None:
    from unittest.mock import patch

    from sfrfr.core import config as cfg

    reset_pending_for_tests()
    storage = Path("storage/test-chat-pending-uploads")
    storage.mkdir(parents=True, exist_ok=True)

    inserted: list[dict] = []

    class _FakeTable:
        def insert(self, row):
            inserted.append(row)
            return self

        def execute(self):
            return type("R", (), {"data": inserted[-1:]})()

    class _FakeClient:
        def table(self, name: str):
            assert name == "case_messages"
            return _FakeTable()

    with patch.dict("os.environ", {"STORAGE_LOCAL_PATH": str(storage.resolve())}):
        cfg.get_settings.cache_clear()
        with patch("sfrfr.db.session.get_supabase_client", return_value=_FakeClient()):
            append_client_case_message(case_id=None, max_user_id="u1", text="Привет")
            append_bot_case_message(
                case_id=None,
                max_user_id="u1",
                text="Выберите шаг",
                attachments=[
                    {
                        "payload": {
                            "buttons": [[{"text": "За себя", "type": "callback"}]],
                        }
                    }
                ],
            )
            assert inserted == []

            case_id = "12345678-1234-1234-1234-123456789012"
            n = flush_pending_case_chat(max_user_id="u1", case_id=case_id)
            assert n == 2
            assert len(inserted) == 2
            assert inserted[0]["body"] == "Привет"
            assert inserted[0]["author_kind"] == "client"
            assert inserted[1]["author_kind"] == "system"
            assert "За себя" in inserted[1]["body"]
            assert "[Кнопки бота:" in inserted[1]["body"]
            assert flush_pending_case_chat(max_user_id="u1", case_id=case_id) == 0

    reset_pending_for_tests()
    cfg.get_settings.cache_clear()
