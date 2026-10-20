"""P0: авто-тип документа в MAX + подтверждение Да/Нет (кликабельные кнопки)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfrfr.integrations.max import document_auto_type as auto
from sfrfr.integrations.max import document_type_flow as dtf
from sfrfr.integrations.max.client import MaxBotClient
from sfrfr.integrations.max.intake import MaxIntakeRecord

# --- авто-определение типа -------------------------------------------------

def test_guess_ils_from_filename() -> None:
    g = auto.guess_document_type(filename="Выписка ИЛС.pdf")
    assert g.doc_type == "ils"
    assert g.confidence >= 0.5


def test_guess_workbook_from_filename() -> None:
    g = auto.guess_document_type(filename="трудовая книжка.jpg")
    assert g.doc_type == "workbook"


def test_guess_ils_from_text_content() -> None:
    text = "Сведения о состоянии индивидуального лицевого счёта застрахованного лица"
    g = auto.guess_document_type(filename="scan.pdf", text=text)
    assert g.doc_type == "ils"


def test_guess_workbook_from_text_content() -> None:
    text = "Трудовая книжка. Сведения о работе: принят на должность, уволен."
    g = auto.guess_document_type(filename="scan.pdf", text=text)
    assert g.doc_type == "workbook"


def test_guess_spravka_from_text() -> None:
    text = "Справка о стаже работы выдана для предъявления"
    g = auto.guess_document_type(filename="doc.pdf", text=text)
    assert g.doc_type == "spravka"


def test_guess_unknown_is_other_low_confidence() -> None:
    g = auto.guess_document_type(filename="photo.jpg", text="")
    assert g.doc_type == "other"
    assert g.confidence < 0.5


def test_guess_receipt_not_auto_receipt() -> None:
    """Gate #151: любой файл != чек. Чек авто-типом не предлагаем."""
    g = auto.guess_document_type(filename="чек оплата.pdf", text="Кассовый чек оплата услуг")
    assert g.doc_type != "payment_receipt"


def test_client_labels_no_latin_no_jargon() -> None:
    for name in ("Выписка ИЛС.pdf", "трудовая.jpg", "справка.pdf", "x.pdf"):
        g = auto.guess_document_type(filename=name)
        assert "PDF" not in g.confirm_text()
        assert "JPG" not in g.confirm_text()
    ils = auto.guess_document_type(filename="ИЛС.pdf")
    assert "выписка о стаже" in ils.confirm_text().lower()
    assert "Правильно?" in ils.confirm_text()


# --- клавиатуры: формат, реально уходящий в MAX API ------------------------

def _assert_max_clickable(keyboard) -> None:
    """MAX рендерит неактивным переполненный ряд: только 1 кнопка в ряд."""
    assert keyboard and keyboard[0]["type"] == "inline_keyboard"
    rows = keyboard[0]["payload"]["buttons"]
    assert rows
    for row in rows:
        assert len(row) == 1, "в MAX кликабельна только 1 кнопка в ряд"
        btn = row[0]
        assert btn["type"] == "callback"
        assert btn["text"].strip()
        assert btn["payload"].strip()


def test_confirm_keyboard_clickable_yes_no() -> None:
    kb = dtf.confirm_keyboard()
    _assert_max_clickable(kb)
    payloads = [r[0]["payload"] for r in kb[0]["payload"]["buttons"]]
    assert payloads == ["max:doc:confirm:yes", "max:doc:confirm:no"]


def test_type_keyboard_clickable_one_per_row() -> None:
    _assert_max_clickable(dtf.type_keyboard())


def test_send_message_body_contains_clickable_keyboard() -> None:
    """Именно тот JSON, что уходит в POST /messages MAX API."""
    client = MaxBotClient(token="t", api_base="https://example.test")
    captured = {}

    class Resp:
        content = b"{}"

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"message": {"id": "1"}}

    class FakeHttp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers=None, params=None, json=None):
            captured.update(json or {})
            return Resp()

    with patch.object(client, "_client", return_value=FakeHttp()):
        client.send_message(
            text="Похоже, вы прислали: выписка о стаже. Правильно?",
            user_id=1,
            attachments=dtf.confirm_keyboard(),
        )
    _assert_max_clickable(captured["attachments"])


# --- подтверждение пишет тип ------------------------------------------------

def _rec_with_guess() -> MaxIntakeRecord:
    rec = MaxIntakeRecord(id="r1", max_user_id="u1", status="started")
    dtf.remember_pending(rec, document_id="doc-9", filename="ils.pdf", guess="ils")
    return rec


def test_confirm_yes_writes_guessed_type_and_confirmed_journal() -> None:
    rec = _rec_with_guess()
    replies: list[tuple[str, object]] = []
    journals: list[dict] = []

    def fake_journal(**kw):
        journals.append(kw)

    with (
        patch.object(dtf, "set_document_type", return_value=True) as set_type,
        patch.object(dtf, "append_type_journal", side_effect=fake_journal),
        patch("sfrfr.integrations.max.document_type_flow.get_intake_store") as store_mod,
    ):
        store_mod.return_value = MagicMock()
        out = dtf.handle(
            rec,
            lambda t, a=None: replies.append((t, a)),
            payload="max:doc:confirm:yes",
            case_id="12345678-1234-1234-1234-123456789012",
        )
    assert out is not None and out[0] == "doc_type_confirmed"
    set_type.assert_called_once_with(document_id="doc-9", doc_type="ils")
    assert journals and journals[0].get("confirmed") is True
    assert journals[0].get("doc_type") == "ils"
    assert dtf.pending_document_id(rec) is None


def test_confirm_no_offers_fallback_list_and_keeps_pending() -> None:
    rec = _rec_with_guess()
    replies: list[tuple[str, object]] = []
    with patch("sfrfr.integrations.max.document_type_flow.get_intake_store") as store_mod:
        store_mod.return_value = MagicMock()
        out = dtf.handle(
            rec,
            lambda t, a=None: replies.append((t, a)),
            payload="max:doc:confirm:no",
            case_id=None,
        )
    assert out is not None and out[0] == "doc_type_rejected"
    assert dtf.pending_document_id(rec) == "doc-9"
    assert replies and replies[0][1]  # приложен запасной список типов
    _assert_max_clickable(replies[0][1])


def test_guess_question_text_is_first_step_not_bare_list() -> None:
    g = auto.guess_document_type(filename="ИЛС.pdf")
    text = dtf.guess_question_text(g)
    assert "Правильно?" in text
    assert "выписка о стаже" in text.lower()
