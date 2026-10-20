"""Пачка файлов: один спокойный ответ, без howto-кнопок, итог после паузы."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from test_max_intake import _msg, _setup

from sfrfr.core.config import get_settings
from sfrfr.integrations.max import document_background as bg
from sfrfr.integrations.max.handler import handle_max_update

CASE_ID = "12345678-1234-1234-1234-123456789012"
USER = "777"


def _prep_upload(tmp_path: Path, monkeypatch, *, filenames: list[str]) -> object:
    from sfrfr.integrations.max import handler as handler_mod

    handler_mod._RECENT_CALLBACKS.clear()
    bg.reset_quiet_state()
    bot = _setup(tmp_path, monkeypatch)
    handle_max_update(_msg(USER, "/start"), bot=bot)
    files = [(name, b"%PDF-1.4 fake") for name in filenames]
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._collect_max_files",
        lambda _u: files,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._try_max_payment_receipt",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._ingest_max_file",
        lambda **_kw: f"doc-{_kw.get('filename', 'x')}",
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._notify_staff_chat_docs",
        lambda **_kw: None,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._chat_case_id",
        lambda _uid, preferred=None: CASE_ID,
    )
    monkeypatch.setattr(bg, "schedule_document_background", lambda **_kw: None)
    monkeypatch.setattr(bg, "schedule_settle_notify", lambda **_kw: None)
    return bot


def test_burst_uploads_one_ack_no_howto_no_next_pressure(tmp_path, monkeypatch) -> None:
    bot = _prep_upload(tmp_path, monkeypatch, filenames=["a.pdf"])
    bot.sent.clear()
    bot.attachments.clear()

    r1 = handle_max_update(_msg(USER, ""), bot=bot)
    assert r1.action == "upload"
    assert len([t for _u, t in bot.sent if t]) == 1
    text1 = bot.sent[-1][1].lower()
    assert "время" in text1 or "обработ" in text1 or "разбор" in text1
    assert "следующ" not in text1
    assert "как получить" not in text1
    assert "трудов" not in text1 or "обработ" in text1  # не howto про трудовую
    flat = str(bot.attachments)
    assert "intake:docs:ils_howto" not in flat
    assert "intake:docs:stazh" not in flat
    assert "max:doc:done" not in flat

    # ещё пять «отдельных» апдейтов как у владельца — без второго ответа
    for _ in range(5):
        r = handle_max_update(_msg(USER, ""), bot=bot)
        assert r.action in {"upload", "upload_quiet"}
    client_texts = [t for _u, t in bot.sent if t]
    assert len(client_texts) == 1
    get_settings.cache_clear()


def test_processing_ack_text_is_calm() -> None:
    text = bg.processing_ack_text(count=3)
    low = text.lower()
    assert "получил" in low or "сохран" in low
    assert "время" in low or "обработ" in low
    assert "напиш" in low or "сообще" in low
    assert "следующ" not in low
    assert "pdf" not in low
    assert "docx" not in low


def test_kit_notify_suppressed_while_quiet() -> None:
    from sfrfr.services import max_kit_status as kit

    bg.reset_quiet_state()
    bg.mark_quiet_ack(USER, case_id=CASE_ID)
    assert bg.is_case_quiet(CASE_ID) is True
    kit.reset_kit_cache()
    with patch(
        "sfrfr.services.case_chat_delivery.enqueue_max_delivery"
    ) as deliver:
        ok = kit.notify_kit_status_after_ingest(
            case_id=CASE_ID, placement_suggestion={}, doc_type="ils"
        )
    assert ok is False
    deliver.assert_not_called()
