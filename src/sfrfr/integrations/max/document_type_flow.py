"""ТЗ-35 C1: после файла в MAX — спросить тип (ИЛС / Трудовая / Другое)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sfrfr.integrations.max.client import inline_buttons_keyboard
from sfrfr.integrations.max.intake import MaxIntakeRecord, get_intake_store

logger = logging.getLogger(__name__)

Reply = Callable[[str, list[dict[str, Any]] | None], Any]

CALLBACK_PREFIX = "max:doc:type:"
CONFIRM_PREFIX = "max:doc:confirm:"
CONFIRM_YES = f"{CONFIRM_PREFIX}yes"
CONFIRM_NO = f"{CONFIRM_PREFIX}no"
TYPE_ILS = "ils"
TYPE_WORKBOOK = "workbook"
TYPE_SPRAVKA = "spravka"
TYPE_OTHER = "other"

DOC_TYPE_LABELS_RU: dict[str, str] = {
    TYPE_ILS: "ИЛС",
    TYPE_WORKBOOK: "Трудовая",
    TYPE_SPRAVKA: "Справка",
    TYPE_OTHER: "Другое",
}

# Полные подписи кнопок запасного списка (по одной в ряд — кликабельность MAX).
DOC_TYPE_BUTTON_LABELS_RU: dict[str, str] = {
    TYPE_ILS: "Выписка о стаже",
    TYPE_WORKBOOK: "Трудовая книжка",
    TYPE_SPRAVKA: "Справка",
    TYPE_OTHER: "Другое",
}

# Подписи для журнала дела (чуть полнее кнопок).
DOC_TYPE_JOURNAL_LABELS_RU: dict[str, str] = {
    TYPE_ILS: "Выписка ИЛС",
    TYPE_WORKBOOK: "Трудовая книжка",
    TYPE_SPRAVKA: "Справка",
    TYPE_OTHER: "Другое",
}

ASK_TYPE_TEXT = (
    "Файл получили. Уточните, пожалуйста, что это за документ — "
    "так специалисту будет проще разобрать дело."
)

# Next step по комплекту (без дубля welcome SFRFR-78 и без сценария оплаты).
_NEXT_KIT_HINT: dict[str, str] = {
    TYPE_ILS: (
        "Следующий шаг: если трудовой ещё нет — пришлите фото или PDF "
        "трудовой книжки (или выписку из электронной трудовой) в этот чат."
    ),
    TYPE_WORKBOOK: (
        "Следующий шаг: если выписки ИЛС ещё нет — получите её на Госуслугах "
        "и пришлите файл сюда в чат."
    ),
    TYPE_SPRAVKA: (
        "Для разбора обычно нужны выписка ИЛС и трудовая. "
        "Пришлите их сюда, когда будут под рукой."
    ),
    TYPE_OTHER: (
        "Для разбора обычно нужны выписка ИЛС и трудовая. "
        "Пришлите их сюда, когда будут под рукой."
    ),
}

_PENDING_ID_KEY = "_pending_doc_id"
_PENDING_NAME_KEY = "_pending_doc_name"
_PENDING_GUESS_KEY = "_pending_doc_guess"
_PENDING_QUEUE_KEY = "_pending_doc_queue"


def type_label(doc_type: str | None) -> str:
    key = str(doc_type or "").strip().lower()
    return DOC_TYPE_LABELS_RU.get(key, key or "документ")


def journal_type_label(doc_type: str | None) -> str:
    key = str(doc_type or "").strip().lower()
    return DOC_TYPE_JOURNAL_LABELS_RU.get(key) or type_label(key)


def kit_next_step_hint(doc_type: str) -> str:
    return _NEXT_KIT_HINT.get(str(doc_type or "").strip().lower(), "")


def received_text(doc_type: str) -> str:
    base = f"Документ получен: «{type_label(doc_type)}»"
    hint = kit_next_step_hint(doc_type)
    if hint:
        return f"{base}\n\n{hint}"
    return base


def received_summary_ru(*, filename: str, doc_type: str | None = None) -> str:
    """Краткое подтверждение клиенту без латиницы форматов и жаргона."""
    from pathlib import Path

    name = Path(filename or "файл").stem.replace("_", " ").strip() or "файл"
    # Убрать хвосты вроде «(1)» от телефона — не пугать цифрами без смысла.
    name = name.replace(" (1)", "").replace("(1)", "").strip() or "файл"
    if doc_type:
        return f"Файл получили — «{name}» ({type_label(doc_type)}). Сейчас разберём."
    return (
        f"Файл получили — «{name}». Сейчас разберём — "
        "уточните, пожалуйста, тип документа кнопкой ниже."
    )


def type_keyboard() -> list[dict[str, Any]]:
    """Запасной список типов. По одной кнопке в ряд: MAX-клиент не нажимает
    переполненный ряд (3 кнопки в ряд у C1 были некликабельны)."""
    return inline_buttons_keyboard(
        [
            [{"type": "callback", "text": label, "payload": f"{CALLBACK_PREFIX}{code}"}]
            for code, label in DOC_TYPE_BUTTON_LABELS_RU.items()
        ]
    )


def confirm_keyboard() -> list[dict[str, Any]]:
    """Да / Нет — по одной кнопке в ряд (кликабельный формат MAX)."""
    return inline_buttons_keyboard(
        [
            [{"type": "callback", "text": "Да, правильно", "payload": CONFIRM_YES}],
            [{"type": "callback", "text": "Нет, другой документ", "payload": CONFIRM_NO}],
        ]
    )


def guess_question_text(guess: Any, *, filename: str = "") -> str:
    """Первый вопрос клиенту: авто-тип + подтверждение, не голый список."""
    del filename
    from sfrfr.integrations.max.document_auto_type import GuessedDocument

    g = guess if isinstance(guess, GuessedDocument) else None
    body = g.confirm_text() if g is not None else "Похоже, это другой документ. Правильно?"
    return f"Файл получили — спасибо! Сейчас разберём.\n\n{body}"


def parse_type_payload(payload: str) -> str | None:
    raw = str(payload or "").strip()
    if not raw.startswith(CALLBACK_PREFIX):
        return None
    code = raw[len(CALLBACK_PREFIX) :].strip().lower()
    if code in DOC_TYPE_LABELS_RU:
        return code
    return None


def pending_document_id(rec: MaxIntakeRecord | None) -> str | None:
    if rec is None:
        return None
    value = str((rec.q_answers or {}).get(_PENDING_ID_KEY) or "").strip()
    return value or None


def pending_guess(rec: MaxIntakeRecord | None) -> str:
    if rec is None:
        return TYPE_OTHER
    value = str((rec.q_answers or {}).get(_PENDING_GUESS_KEY) or "").strip().lower()
    return value if value in DOC_TYPE_LABELS_RU else TYPE_OTHER


def remember_pending(
    rec: MaxIntakeRecord,
    *,
    document_id: str,
    filename: str,
    guess: str = TYPE_OTHER,
) -> None:
    """Запомнить документ и авто-тип, для которого ждём подтверждение."""
    answers = dict(rec.q_answers or {})
    doc_id = str(document_id or "").strip()
    name = str(filename or "файл").strip() or "файл"
    guessed = str(guess or TYPE_OTHER).strip().lower()
    if guessed not in DOC_TYPE_LABELS_RU:
        guessed = TYPE_OTHER
    if not doc_id:
        return
    current = str(answers.get(_PENDING_ID_KEY) or "").strip()
    if current and current != doc_id:
        queue_raw = str(answers.get(_PENDING_QUEUE_KEY) or "").strip()
        parts = [p for p in queue_raw.split("|") if p]
        parts.append(f"{doc_id}::{name}::{guessed}")
        answers[_PENDING_QUEUE_KEY] = "|".join(parts[-20:])
        rec.q_answers = answers
        get_intake_store().save(rec)
        return
    answers[_PENDING_ID_KEY] = doc_id
    answers[_PENDING_NAME_KEY] = name
    answers[_PENDING_GUESS_KEY] = guessed
    rec.q_answers = answers
    get_intake_store().save(rec)


def clear_pending(rec: MaxIntakeRecord) -> None:
    answers = dict(rec.q_answers or {})
    answers.pop(_PENDING_ID_KEY, None)
    answers.pop(_PENDING_NAME_KEY, None)
    answers.pop(_PENDING_GUESS_KEY, None)
    queue_raw = str(answers.get(_PENDING_QUEUE_KEY) or "").strip()
    parts = [p for p in queue_raw.split("|") if p]
    if parts:
        nxt = parts.pop(0)
        answers[_PENDING_QUEUE_KEY] = "|".join(parts)
        fields = nxt.split("::")
        doc_id = fields[0] if fields else nxt
        name = fields[1] if len(fields) > 1 and fields[1] else "файл"
        guess = fields[2] if len(fields) > 2 and fields[2] in DOC_TYPE_LABELS_RU else TYPE_OTHER
        answers[_PENDING_ID_KEY] = doc_id
        answers[_PENDING_NAME_KEY] = name
        answers[_PENDING_GUESS_KEY] = guess
    else:
        answers.pop(_PENDING_QUEUE_KEY, None)
    rec.q_answers = answers
    get_intake_store().save(rec)


def set_document_type(*, document_id: str, doc_type: str) -> bool:
    """Записать doc_type в documents. False при ошибке."""
    from sfrfr.db.supabase_client import get_supabase_client

    doc_id = str(document_id or "").strip()
    dtype = str(doc_type or "").strip().lower()
    if not doc_id or dtype not in DOC_TYPE_LABELS_RU:
        return False
    try:
        get_supabase_client().table("documents").update({"doc_type": dtype}).eq(
            "id", doc_id
        ).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("doc_type update failed id=%s: %s", doc_id[:8], exc)
        return False


def append_type_journal(
    *,
    case_id: str | None,
    filename: str,
    doc_type: str,
    confirmed: bool = False,
) -> None:
    from sfrfr.integrations.max.case_chat_log import (
        append_case_chat_message,
        format_document_event,
    )

    cid = str(case_id or "").strip()
    if not cid:
        return
    if confirmed:
        name = (filename or "файл").strip() or "файл"
        body = f"[Документ] {name} · Клиент подтвердил: {journal_type_label(doc_type)}"
    else:
        body = format_document_event(filename=filename, doc_type=doc_type)
    try:
        append_case_chat_message(
            case_id=cid,
            author_kind="system",
            body=body,
            channel_origin="bot",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("doc_type journal failed: %s", exc)


def handle(
    rec: MaxIntakeRecord,
    reply: Reply,
    *,
    payload: str,
    case_id: str | None,
) -> tuple[str, str] | None:
    """Обработать max:doc:confirm:* и max:doc:type:*. None — чужой payload."""
    raw = str(payload or "").strip()
    filename = str((rec.q_answers or {}).get(_PENDING_NAME_KEY) or "файл").strip() or "файл"

    if raw == CONFIRM_NO:
        if not pending_document_id(rec):
            return None
        text = (
            "Поняли, спасибо. Уточните, пожалуйста, что это за документ — "
            "выберите кнопкой ниже."
        )
        reply(text, type_keyboard())
        return "doc_type_rejected", text

    confirmed = raw == CONFIRM_YES
    if confirmed:
        doc_type = pending_guess(rec)
    else:
        parsed = parse_type_payload(raw)
        if parsed is None:
            return None
        doc_type = parsed

    doc_id = pending_document_id(rec)
    if not doc_id:
        text = (
            "Не нашли файл, для которого определяли тип. "
            "Пришлите документ ещё раз, пожалуйста."
        )
        reply(text, None)
        return "doc_type_missing", text

    ok = set_document_type(document_id=doc_id, doc_type=doc_type)
    text = received_text(doc_type)
    if not ok:
        text = (
            f"{text}\n"
            "Тип записали для вас; если в кабинете не отобразится — "
            "специалист уточнит по файлу."
        )
    append_type_journal(
        case_id=case_id, filename=filename, doc_type=doc_type, confirmed=confirmed
    )
    try:
        clear_pending(rec)
    except Exception as exc:  # noqa: BLE001 — ответ клиенту важнее чистки pending
        logger.warning("doc_type clear_pending failed: %s", exc)
    next_id = pending_document_id(rec)
    attachments = None
    if next_id:
        from sfrfr.integrations.max.document_auto_type import GuessedDocument

        nxt_guess = GuessedDocument(pending_guess(rec), 0.65)
        text = f"{text}\n\nЕщё один файл.\n\n{nxt_guess.confirm_text()}"
        attachments = confirm_keyboard()
    reply(text, attachments)
    return ("doc_type_confirmed" if confirmed else "doc_type_set"), text
