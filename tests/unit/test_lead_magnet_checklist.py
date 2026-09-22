"""Лид-магнит: выдача чек-листа документов для анализа дела."""

from __future__ import annotations

from sfrfr.services.lead_magnet_checklist import (
    LEAD_MAGNET_PDF_URL,
    build_lead_magnet_message,
    is_lead_magnet_request,
)


def test_build_message_lists_docs_for_analysis() -> None:
    text = build_lead_magnet_message(name="Елена")
    lower = text.lower()
    assert "елена" in lower
    assert "илс" in lower or "сзи" in lower
    assert "трудов" in lower
    assert LEAD_MAGNET_PDF_URL in text
    assert "анализ" in lower or "проверк" in lower
    assert "принимает только сфр" in lower
    assert "вернём" not in lower and "увеличим" not in lower
    assert "не отправ" in lower
    assert "канал max" in lower
    assert "чат-бот" in lower or "чат бот" in lower
    assert "личный чат" in lower


def test_build_message_without_name() -> None:
    text = build_lead_magnet_message()
    assert "Здравствуйте!" in text
    assert "ИЛС получил" in text or "ИЛС получил(а)" in text


def test_is_lead_magnet_request_phrases() -> None:
    assert is_lead_magnet_request("Нужен чек-лист документов")
    assert is_lead_magnet_request("нужен чеклист")
    assert is_lead_magnet_request("/checklist")
    assert is_lead_magnet_request("чек-лист документов")
    assert not is_lead_magnet_request("нужна проверка")
    assert not is_lead_magnet_request("дорого")


def test_max_handler_sends_lead_magnet_checklist(tmp_path, monkeypatch) -> None:
    from pathlib import Path

    from sfrfr.core.case_store import reset_case_store
    from sfrfr.core.config import get_settings
    from sfrfr.integrations.max.handler import handle_max_update
    from sfrfr.integrations.max.intake import reset_intake_store

    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path / "uploads"))
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setenv("OPS_NOTIFY_EMAIL", "")
    monkeypatch.setenv("MAX_LLM_CHAT_ENABLED", "0")
    get_settings.cache_clear()
    reset_case_store(Path(tmp_path) / "cases.json")
    reset_intake_store(Path(tmp_path) / "max_intake.json")
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._client_has_pdn_consent",
        lambda _uid: True,
    )

    class _Bot:
        def __init__(self) -> None:
            self.sent: list[str] = []

        @property
        def available(self) -> bool:
            return True

        def send_message(self, *, text, user_id=None, chat_id=None, attachments=None, **_):
            self.sent.append(text)
            return {"ok": True}

        def send_chat_action(self, **_):
            return {"ok": True}

    bot = _Bot()
    update = {
        "message": {
            "sender": {"user_id": 42},
            "recipient": {"chat_id": 1, "chat_type": "dialog"},
            "body": {"text": "Нужен чек-лист документов"},
        }
    }
    result = handle_max_update(update, bot=bot)
    assert result.action == "lead_magnet_checklist"
    assert bot.sent
    assert "ИЛС" in bot.sent[0]
    assert LEAD_MAGNET_PDF_URL in bot.sent[0]
    get_settings.cache_clear()
