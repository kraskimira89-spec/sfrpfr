"""Новый сценарий: без вопроса о типе, фон, «это всё»."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from test_max_doc_confirm_e2e import _real_max_callback
from test_max_intake import _msg, _setup

from sfrfr.core.config import get_settings
from sfrfr.integrations.max import document_background as bg
from sfrfr.integrations.max import document_type_flow as dtf
from sfrfr.integrations.max.handler import handle_max_update

CASE_ID = "12345678-1234-1234-1234-123456789012"
USER = 888


def _upload(tmp_path: Path, monkeypatch, scheduled: list) -> object:
    from sfrfr.integrations.max import handler as handler_mod

    handler_mod._RECENT_CALLBACKS.clear()
    bg.reset_quiet_state()
    bot = _setup(tmp_path, monkeypatch)
    handle_max_update(_msg(USER, "/start"), bot=bot)
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._collect_max_files",
        lambda _u: [("Выписка ИЛС.pdf", b"%PDF-1.4 fake")],
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._try_max_payment_receipt",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._ingest_max_file", lambda **_kw: "doc-1"
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._notify_staff_chat_docs", lambda **_kw: None
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._chat_case_id",
        lambda _uid, preferred=None: CASE_ID,
    )
    monkeypatch.setattr(bg, "schedule_document_background", lambda **kw: scheduled.append(kw))
    monkeypatch.setattr(bg, "schedule_settle_notify", lambda **_kw: None)
    with patch(
        "sfrfr.integrations.max.document_auto_type.guess_from_bytes",
        side_effect=AssertionError("тип нельзя определять синхронно"),
    ):
        up = handle_max_update(_msg(USER, ""), bot=bot)
    assert up.action == "upload"
    return bot


def test_upload_saved_no_type_question_schedules_background(tmp_path, monkeypatch) -> None:
    scheduled: list = []
    bot = _upload(tmp_path, monkeypatch, scheduled)
    joined = "\n".join(t for _u, t in bot.sent if t)
    low = joined.lower()
    assert "получил" in low or "обработ" in low
    assert "время" in low or "разбор" in low
    assert "следующ" not in low
    flat = str([a for a in bot.attachments if a])
    assert "max:doc:done" not in flat
    assert "max:doc:confirm:" not in flat
    assert "max:doc:type:" not in flat
    assert "Правильно?" not in joined
    assert scheduled and scheduled[0]["document_id"] == "doc-1"
    get_settings.cache_clear()


def test_background_writes_type_and_journal() -> None:
    from sfrfr.integrations.max.document_auto_type import GuessedDocument

    with (
        patch(
            "sfrfr.integrations.max.document_auto_type.guess_from_bytes",
            return_value=GuessedDocument("ils", 0.8),
        ),
        patch.object(dtf, "set_document_type", return_value=True) as set_type,
        patch.object(dtf, "append_type_journal") as journal,
    ):
        result = bg.analyze_document_background(
            case_id=CASE_ID, document_id="doc-1", filename="scan.pdf", data=b"x"
        )
    assert result == "ils"
    set_type.assert_called_once_with(document_id="doc-1", doc_type="ils")
    assert journal.called and journal.call_args.kwargs["doc_type"] == "ils"


def test_final_incomplete_requests_missing() -> None:
    text, complete = bg.build_final_message(
        [{"doc_type": "ils", "storage_path": "x/Выписка.pdf"}]
    )
    assert complete is False
    assert "выписка о стаже" in text.lower()
    assert "трудов" in text.lower()


def test_final_complete_proposes_analysis_without_promises() -> None:
    text, complete = bg.build_final_message(
        [
            {"doc_type": "ils", "storage_path": "x/a.pdf"},
            {"doc_type": "workbook", "storage_path": "x/b.pdf"},
        ]
    )
    assert complete is True
    assert "приступать к анализу" in text.lower() or "анализ" in text.lower()
    assert "подаёте" in text.lower()
    assert "СФР" in text
    assert "перерасчёт будет" not in text.lower()


def test_done_button_incomplete_and_complete(tmp_path, monkeypatch) -> None:
    scheduled: list = []
    bot = _upload(tmp_path, monkeypatch, scheduled)
    with patch.object(
        bg, "final_message_for_case", return_value=("Итог: нужна трудовая книжка.", False)
    ):
        out = handle_max_update(
            _real_max_callback(bg.DONE_PAYLOAD, callback_id="cb-done1"), bot=bot
        )
    assert out.action == "docs_done_incomplete"
    assert "трудовая" in (out.reply or "")
    from sfrfr.integrations.max import handler as handler_mod

    handler_mod._RECENT_CALLBACKS.clear()
    with patch.object(
        bg, "final_message_for_case", return_value=("Итог: можно приступить к анализу.", True)
    ):
        out2 = handle_max_update(
            _real_max_callback(bg.DONE_PAYLOAD, callback_id="cb-done2"), bot=bot
        )
    assert out2.action == "docs_done_complete"
    get_settings.cache_clear()


def test_done_text_command(tmp_path, monkeypatch) -> None:
    scheduled: list = []
    bot = _upload(tmp_path, monkeypatch, scheduled)
    assert bg.is_done_text("Это всё")
    assert bg.is_done_text("больше нет")
    with patch.object(
        bg, "final_message_for_case", return_value=("Итог: нужна трудовая книжка.", False)
    ):
        out = handle_max_update(_msg(USER, "это всё"), bot=bot)
    assert out.action == "docs_done_incomplete"
    get_settings.cache_clear()


def test_legacy_confirm_callback_does_not_crash(tmp_path, monkeypatch) -> None:
    scheduled: list = []
    bot = _upload(tmp_path, monkeypatch, scheduled)
    out = handle_max_update(
        _real_max_callback("max:doc:confirm:yes", callback_id="cb-legacy1"), bot=bot
    )
    assert out is not None
    get_settings.cache_clear()
