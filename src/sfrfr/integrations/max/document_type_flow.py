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
TYPE_ILS = "ils"
TYPE_WORKBOOK = "workbook"
TYPE_OTHER = "other"

DOC_TYPE_LABELS_RU: dict[str, str] = {
    TYPE_ILS: "ИЛС",
    TYPE_WORKBOOK: "Трудовая",
    TYPE_OTHER: "Другое",
}

# Подписи для журнала дела (чуть полнее кнопок).
DOC_TYPE_JOURNAL_LABELS_RU: dict[str, str] = {
    TYPE_ILS: "Выписка ИЛС",
    TYPE_WORKBOOK: "Трудовая книжка",
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
    TYPE_OTHER: (
        "Для разбора обычно нужны выписка ИЛС и трудовая. "
        "Пришлите их сюда, когда будут под рукой."
    ),
}

_PENDING_ID_KEY = "_pending_doc_id"
_PENDING_NAME_KEY = "_pending_doc_name"
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


def type_keyboard() -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [
                {
                    "type": "callback",
                    "text": DOC_TYPE_LABELS_RU[TYPE_ILS],
                    "payload": f"{CALLBACK_PREFIX}{TYPE_ILS}",
                },
                {
                    "type": "callback",
                    "text": DOC_TYPE_LABELS_RU[TYPE_WORKBOOK],
                    "payload": f"{CALLBACK_PREFIX}{TYPE_WORKBOOK}",
                },
                {
                    "type": "callback",
                    "text": DOC_TYPE_LABELS_RU[TYPE_OTHER],
                    "payload": f"{CALLBACK_PREFIX}{TYPE_OTHER}",
                },
            ]
        ]
    )


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


def remember_pending(
    rec: MaxIntakeRecord,
    *,
    document_id: str,
    filename: str,
) -> None:
    """Запомнить документ, для которого ждём тип (один активный + очередь)."""
    answers = dict(rec.q_answers or {})
    doc_id = str(document_id or "").strip()
    name = str(filename or "файл").strip() or "файл"
    if not doc_id:
        return
    current = str(answers.get(_PENDING_ID_KEY) or "").strip()
    if current and current != doc_id:
        queue_raw = str(answers.get(_PENDING_QUEUE_KEY) or "").strip()
        parts = [p for p in queue_raw.split("|") if p]
        parts.append(f"{doc_id}::{name}")
        answers[_PENDING_QUEUE_KEY] = "|".join(parts[-20:])
        rec.q_answers = answers
        get_intake_store().save(rec)
        return
    answers[_PENDING_ID_KEY] = doc_id
    answers[_PENDING_NAME_KEY] = name
    rec.q_answers = answers
    get_intake_store().save(rec)


def clear_pending(rec: MaxIntakeRecord) -> None:
    answers = dict(rec.q_answers or {})
    answers.pop(_PENDING_ID_KEY, None)
    answers.pop(_PENDING_NAME_KEY, None)
    queue_raw = str(answers.get(_PENDING_QUEUE_KEY) or "").strip()
    parts = [p for p in queue_raw.split("|") if p]
    if parts:
        nxt = parts.pop(0)
        answers[_PENDING_QUEUE_KEY] = "|".join(parts)
        if "::" in nxt:
            doc_id, name = nxt.split("::", 1)
        else:
            doc_id, name = nxt, "файл"
        answers[_PENDING_ID_KEY] = doc_id
        answers[_PENDING_NAME_KEY] = name or "файл"
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
) -> None:
    from sfrfr.integrations.max.case_chat_log import (
        append_case_chat_message,
        format_document_event,
    )

    cid = str(case_id or "").strip()
    if not cid:
        return
    try:
        append_case_chat_message(
            case_id=cid,
            author_kind="system",
            body=format_document_event(
                filename=filename,
                doc_type=doc_type,
            ),
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
    """Обработать max:doc:type:*. None — чужой payload."""
    doc_type = parse_type_payload(payload)
    if doc_type is None:
        return None

    doc_id = pending_document_id(rec)
    filename = str((rec.q_answers or {}).get(_PENDING_NAME_KEY) or "файл").strip() or "файл"
    if not doc_id:
        text = (
            "Не нашли файл, для которого выбирали тип. "
            "Пришлите документ ещё раз — и снова выберите тип."
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
    append_type_journal(case_id=case_id, filename=filename, doc_type=doc_type)
    clear_pending(rec)
    next_id = pending_document_id(rec)
    attachments = type_keyboard() if next_id else None
    if next_id:
        text = f"{text}\n\n{ASK_TYPE_TEXT}"
    reply(text, attachments)
    return "doc_type_set", text
