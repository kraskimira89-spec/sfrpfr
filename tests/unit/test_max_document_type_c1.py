"""ТЗ-35 C1: кнопки типа документа после загрузки в MAX."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfrfr.integrations.max import document_type_flow as dtf
from sfrfr.integrations.max.case_chat_log import (
    format_button_press,
    format_document_event,
    label_for_callback,
)
from sfrfr.integrations.max.intake import MaxIntakeRecord


def test_type_keyboard_payloads() -> None:
    kb = dtf.type_keyboard()
    assert kb
    payload = kb[0]["payload"]
    buttons = payload["buttons"]
    flat = [btn for row in buttons for btn in row]
    texts = {b["text"] for b in flat}
    payloads = {b["payload"] for b in flat}
    assert texts == {"ИЛС", "Трудовая", "Другое"}
    assert payloads == {
        "max:doc:type:ils",
        "max:doc:type:workbook",
        "max:doc:type:other",
    }


def test_received_text_ru() -> None:
    assert dtf.received_text("ils") == "Документ получен: «ИЛС»"
    assert dtf.received_text("workbook") == "Документ получен: «Трудовая»"
    assert dtf.received_text("other") == "Документ получен: «Другое»"


def test_format_document_event_ru_labels() -> None:
    assert (
        format_document_event(filename="scan.pdf", doc_type="ils")
        == "[Документ] scan.pdf · Выписка ИЛС"
    )
    assert "Трудовая" in format_document_event(filename="tk.pdf", doc_type="workbook")
    assert "Другое" in format_document_event(filename="x.pdf", doc_type="other")


def test_button_press_type_human() -> None:
    assert "ИЛС" in format_button_press("max:doc:type:ils")
    assert "max:doc:type:ils" not in format_button_press("max:doc:type:ils")
    assert label_for_callback("max:doc:type:workbook") == "Трудовая"
    assert "тип документа" in format_button_press("max:doc:type:other").lower()


def test_button_press_unknown_no_raw_payload() -> None:
    text = format_button_press("max:foo:bar")
    assert "max:foo:bar" not in text
    assert "max → foo → bar" not in text
    assert "кнопк" in text.lower()


def test_handle_type_callback_updates_doc_and_clears_pending() -> None:
    rec = MaxIntakeRecord(id="r1", max_user_id="u1", status="started")
    dtf.remember_pending(rec, document_id="doc-42", filename="ils.pdf")
    assert dtf.pending_document_id(rec) == "doc-42"

    replies: list[tuple[str, object]] = []

    def reply(text: str, attachments=None) -> None:
        replies.append((text, attachments))

    with (
        patch.object(dtf, "set_document_type", return_value=True) as set_type,
        patch.object(dtf, "append_type_journal") as journal,
        patch("sfrfr.integrations.max.document_type_flow.get_intake_store") as store_mod,
    ):
        store_mod.return_value = MagicMock()
        out = dtf.handle(
            rec,
            reply,
            payload="max:doc:type:ils",
            case_id="12345678-1234-1234-1234-123456789012",
        )

    assert out is not None
    assert out[0] == "doc_type_set"
    assert "Документ получен: «ИЛС»" in out[1]
    set_type.assert_called_once_with(document_id="doc-42", doc_type="ils")
    journal.assert_called_once()
    assert dtf.pending_document_id(rec) is None
    assert replies and "ИЛС" in replies[0][0]


def test_handle_ignores_foreign_payload() -> None:
    rec = MaxIntakeRecord(id="r1", max_user_id="u1", status="started")
    assert dtf.handle(rec, lambda *_a, **_k: None, payload="intake:ils:yes", case_id=None) is None
