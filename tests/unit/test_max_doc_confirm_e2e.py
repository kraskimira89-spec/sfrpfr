"""Старые кнопки подтверждения типа: новых не шлём, старые не роняют handler."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from test_max_intake import _msg, _setup

from sfrfr.core.config import get_settings
from sfrfr.integrations.max import document_type_flow as dtf
from sfrfr.integrations.max.handler import handle_max_update
from sfrfr.integrations.max.intake import get_intake_store

CASE_ID = "12345678-1234-1234-1234-123456789012"
USER = 777


def _real_max_callback(payload: str, *, callback_id: str) -> dict:
    """Апдейт в том виде, как его шлёт platform-api MAX."""
    return {
        "update_type": "message_callback",
        "timestamp": 1760000000000,
        "callback": {
            "callback_id": callback_id,
            "payload": payload,
            "user": {"user_id": USER, "first_name": "Иван", "name": "Иван П."},
        },
        "message": {
            "sender": {"user_id": 1000001, "name": "Проверка стажа"},
            "recipient": {"chat_id": 555, "chat_type": "dialog"},
            "body": {"mid": "mid-1", "seq": 1, "text": "Файл сохранён."},
        },
        "user_locale": "ru",
    }


def _upload_step(tmp_path: Path, monkeypatch) -> object:
    from sfrfr.integrations.max import handler as handler_mod

    handler_mod._RECENT_CALLBACKS.clear()
    bot = _setup(tmp_path, monkeypatch)
    handle_max_update(_msg(USER, "/start"), bot=bot)
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._collect_max_files",
        lambda _update: ([("Выписка ИЛС.pdf", b"%PDF-1.4 fake")], []),
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._try_max_payment_receipt",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._ingest_max_file", lambda **kw: "doc-777"
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._notify_staff_chat_docs", lambda **_kw: None
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._chat_case_id",
        lambda _uid, preferred=None: CASE_ID,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.document_background.schedule_document_background",
        lambda **_kw: None,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.document_background.schedule_settle_notify",
        lambda **_kw: None,
    )
    from sfrfr.integrations.max import document_background as bg

    bg.reset_quiet_state()
    up = handle_max_update(_msg(USER, ""), bot=bot)
    assert up.action == "upload"
    return bot


def test_upload_has_no_confirm_buttons(tmp_path: Path, monkeypatch) -> None:
    bot = _upload_step(tmp_path, monkeypatch)
    flat = str([a for a in bot.attachments if a])
    assert "max:doc:done" not in flat
    assert "max:doc:confirm:" not in flat
    assert "max:doc:type:" not in flat
    joined = "\n".join(t for _u, t in bot.sent if t)
    low = joined.lower()
    assert "получил" in low or "обработ" in low
    assert "следующ" not in low
    get_settings.cache_clear()


def test_legacy_confirm_without_pending_does_not_crash(
    tmp_path: Path, monkeypatch
) -> None:
    bot = _upload_step(tmp_path, monkeypatch)
    result = handle_max_update(
        _real_max_callback("max:doc:confirm:yes", callback_id="cb-legacy"), bot=bot
    )
    assert result is not None
    assert result.action == "doc_type_missing"
    get_settings.cache_clear()


def test_legacy_confirm_with_pending_still_writes_type(
    tmp_path: Path, monkeypatch
) -> None:
    bot = _upload_step(tmp_path, monkeypatch)
    rec = get_intake_store().get_active(str(USER))
    assert rec is not None
    dtf.remember_pending(rec, document_id="doc-777", filename="ils.pdf", guess="ils")
    with (
        patch.object(dtf, "set_document_type", return_value=True),
        patch.object(dtf, "append_type_journal"),
    ):
        result = handle_max_update(
            _real_max_callback("max:doc:confirm:yes", callback_id="cb-legacy2"), bot=bot
        )
    assert result.action == "doc_type_confirmed"
    get_settings.cache_clear()
