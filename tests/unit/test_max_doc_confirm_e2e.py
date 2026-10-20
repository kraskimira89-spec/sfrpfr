"""P0 smoke: «Да, правильно» в MAX end-to-end через handle_max_update.

Формат callback — как присылает реальный MAX API (message_callback),
а не упрощённый {"callback": {...}} из старых тестов.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from test_max_intake import _msg, _setup

from sfrfr.core.config import get_settings
from sfrfr.integrations.max import document_type_flow as dtf
from sfrfr.integrations.max.document_auto_type import GuessedDocument
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
            "body": {
                "mid": "mid-1",
                "seq": 1,
                "text": "Файл получили — спасибо! Сейчас разберём.",
            },
        },
        "user_locale": "ru",
    }


def _upload_step(tmp_path: Path, monkeypatch) -> object:
    from sfrfr.integrations.max import handler as handler_mod

    handler_mod._RECENT_CALLBACKS.clear()
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._client_has_pdn_consent",
        lambda _uid: True,
    )
    start = handle_max_update(_msg(USER, "/start"), bot=bot)
    case_id = start.case_id or CASE_ID
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._collect_max_files",
        lambda _update: [("Выписка ИЛС.pdf", b"%PDF-1.4 fake")],
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._try_max_payment_receipt",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._ingest_max_file",
        lambda **kw: "doc-777",
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._notify_staff_chat_docs",
        lambda **_kw: None,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._chat_case_id",
        lambda _uid, preferred=None: case_id,
    )
    with patch(
        "sfrfr.integrations.max.document_auto_type.guess_from_bytes",
        return_value=GuessedDocument("ils", 0.8),
    ):
        up = handle_max_update(_msg(USER, ""), bot=bot)
    assert up.action == "upload"
    return bot


def test_upload_offers_confirm_yes_no_buttons(tmp_path: Path, monkeypatch) -> None:
    bot = _upload_step(tmp_path, monkeypatch)
    flat = [a for a in bot.attachments if a]
    assert flat, "после загрузки бот должен прислать кнопки подтверждения"
    text = str(flat[-1])
    assert "max:doc:confirm:yes" in text
    assert "max:doc:confirm:no" in text
    rec = get_intake_store().get_active(str(USER))
    assert dtf.pending_document_id(rec) == "doc-777"
    get_settings.cache_clear()


def test_confirm_yes_end_to_end_writes_type_and_replies_next_step(
    tmp_path: Path, monkeypatch
) -> None:
    bot = _upload_step(tmp_path, monkeypatch)
    sent_before = len(bot.sent)

    with (
        patch.object(dtf, "set_document_type", return_value=True) as set_type,
        patch.object(dtf, "append_type_journal") as journal,
    ):
        result = handle_max_update(
            _real_max_callback("max:doc:confirm:yes", callback_id="cb-e2e-yes"),
            bot=bot,
        )

    assert result.action == "doc_type_confirmed"
    set_type.assert_called_once_with(document_id="doc-777", doc_type="ils")
    assert journal.called
    rec = get_intake_store().get_active(str(USER))
    assert dtf.pending_document_id(rec) is None
    new_texts = [t for _uid, t in bot.sent[sent_before:] if t]
    assert new_texts, "после «Да» клиент должен получить следующее сообщение"
    joined = "\n".join(new_texts)
    assert "Документ получен" in joined
    assert "трудов" in joined.lower()  # следующий шаг комплекта после ИЛС
    get_settings.cache_clear()


def test_confirm_no_end_to_end_offers_type_list(tmp_path: Path, monkeypatch) -> None:
    bot = _upload_step(tmp_path, monkeypatch)
    sent_before = len(bot.sent)

    result = handle_max_update(
        _real_max_callback("max:doc:confirm:no", callback_id="cb-e2e-no"),
        bot=bot,
    )

    assert result.action == "doc_type_rejected"
    rec = get_intake_store().get_active(str(USER))
    assert dtf.pending_document_id(rec) == "doc-777"
    new_texts = [t for _uid, t in bot.sent[sent_before:] if t]
    assert new_texts
    flat = [a for a in bot.attachments if a]
    assert "max:doc:type:workbook" in str(flat[-1])
    get_settings.cache_clear()


def test_repeat_press_within_cooldown_not_silent(
    tmp_path: Path, monkeypatch
) -> None:
    """Повторное нажатие «Да» в течение кулдауна: бот не должен молчать."""
    bot = _upload_step(tmp_path, monkeypatch)
    with patch.object(dtf, "set_document_type", return_value=True), patch.object(
        dtf, "append_type_journal"
    ):
        first = handle_max_update(
            _real_max_callback("max:doc:confirm:yes", callback_id="cb-r1"), bot=bot
        )
        assert first.action == "doc_type_confirmed"
        sent_before = len(bot.sent)
        second = handle_max_update(
            _real_max_callback("max:doc:confirm:yes", callback_id="cb-r2"), bot=bot
        )
    assert second.action == "duplicate_payload_cooldown"
    new_texts = [t for _uid, t in bot.sent[sent_before:] if t]
    assert new_texts, "повторное нажатие не должно уходить в тишину"
    get_settings.cache_clear()


def test_confirm_yes_pings_staff(tmp_path: Path, monkeypatch) -> None:
    """После подтверждения типа специалист получает пинг в MAX."""
    bot = _upload_step(tmp_path, monkeypatch)
    pings: list[dict] = []

    def fake_ping(**kw):
        pings.append(kw)
        return True

    with (
        patch.object(dtf, "set_document_type", return_value=True),
        patch.object(dtf, "append_type_journal"),
        patch(
            "sfrfr.integrations.max.staff_client_ping.notify_staff_client_message",
            side_effect=fake_ping,
        ),
    ):
        result = handle_max_update(
            _real_max_callback("max:doc:confirm:yes", callback_id="cb-ping1"),
            bot=bot,
        )
    assert result.action == "doc_type_confirmed"
    assert pings, "специалист должен получить пинг о подтверждении типа"
    assert pings[0].get("kind") == "doc_type"
    get_settings.cache_clear()


def test_confirm_yes_reply_even_if_pending_save_fails(
    tmp_path: Path, monkeypatch
) -> None:
    """Сбой сохранения pending не должен съедать ответ клиенту."""
    bot = _upload_step(tmp_path, monkeypatch)
    sent_before = len(bot.sent)

    def boom(_rec):
        raise OSError("disk full")

    with (
        patch.object(dtf, "set_document_type", return_value=True),
        patch.object(dtf, "append_type_journal"),
        patch.object(dtf, "clear_pending", side_effect=boom),
    ):
        result = handle_max_update(
            _real_max_callback("max:doc:confirm:yes", callback_id="cb-savefail"),
            bot=bot,
        )
    assert result.action == "doc_type_confirmed"
    new_texts = [t for _uid, t in bot.sent[sent_before:] if t]
    assert new_texts and "Документ получен" in new_texts[-1]
    get_settings.cache_clear()


def test_callback_without_callback_id_still_processed(
    tmp_path: Path, monkeypatch
) -> None:
    """MAX может прислать callback без callback_id в части клиентов."""
    bot = _upload_step(tmp_path, monkeypatch)
    update = _real_max_callback("max:doc:confirm:yes", callback_id="cb-x")
    del update["callback"]["callback_id"]

    with patch.object(dtf, "set_document_type", return_value=True):
        result = handle_max_update(update, bot=bot)
    assert result.action == "doc_type_confirmed"
    get_settings.cache_clear()
