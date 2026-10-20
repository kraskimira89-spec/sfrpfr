"""Новый сценарий приёма: сразу «сохранён», тип — фоном, итог по «это всё».

Фоновый разбор переиспользует guess_from_bytes (OCR/classify) и запись
doc_type/журнала из document_type_flow. Запуск — daemon-поток после ответа
клиенту: durable OCR/ingest по-прежнему идёт через document_ingest_worker,
а этот поток только дозаполняет тип. Ограничение: если процесс умрёт до
конца потока, тип останется пустым — файл при этом уже сохранён (local-first)
и виден специалисту в деле, повторный разбор возможен из кабинета/worker.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from sfrfr.integrations.max import document_type_flow as dtf
from sfrfr.integrations.max.client import inline_buttons_keyboard
from sfrfr.integrations.max.document_auto_type import CLIENT_LABELS_RU

logger = logging.getLogger(__name__)

DONE_PAYLOAD = "max:doc:done"
DONE_LABEL = "Это все документы"
_DONE_TEXTS = {"это всё", "это все", "больше нет", "всё", "все", "готово", "хватит"}

_HUMAN_BY_TYPE = {
    "ils": "выписка о стаже",
    "ils_statement": "выписка о стаже",
    "workbook": "трудовая книжка",
    "labor_book": "трудовая книжка",
    "labor": "трудовая книжка",
    "spravka": "справка",
    "other": "другой документ",
}
_MISSING_RU = {"ils": "выписки о стаже", "labor": "трудовой книжки"}


def done_keyboard() -> list[dict[str, Any]]:
    """Одна кнопка в ряд — тот же кликабельный формат, что у кнопок согласия."""
    return inline_buttons_keyboard(
        [[{"type": "callback", "text": DONE_LABEL, "payload": DONE_PAYLOAD}]]
    )


def is_done_text(text: str) -> bool:
    clean = " ".join(str(text or "").strip().lower().replace("ё", "е").split()).strip(" .!")
    return clean in _DONE_TEXTS


def saved_text(filename: str, *, count: int = 1) -> str:
    if count > 1:
        return (
            f"Файлы сохранены — получили {count}. Спасибо!\n\n"
            "Пришлите, пожалуйста, следующий документ, если он есть. "
            "Если документов больше нет — нажмите кнопку ниже."
        )
    name = Path(filename or "файл").stem.replace("_", " ").strip() or "файл"
    return (
        f"Файл сохранён — «{name}». Спасибо!\n\n"
        "Пришлите, пожалуйста, следующий документ, если он есть. "
        "Если документов больше нет — нажмите кнопку ниже."
    )


def _bucket(doc: dict[str, Any]) -> str:
    try:
        from sfrfr.services.max_kit_status import classify_doc_bucket

        placement = doc.get("placement_suggestion")
        return classify_doc_bucket(
            placement if isinstance(placement, dict) else {}, str(doc.get("doc_type") or "")
        )
    except Exception:  # noqa: BLE001
        dtype = str(doc.get("doc_type") or "").strip().lower()
        if dtype in {"ils", "ils_statement"}:
            return "ils"
        if dtype in {"workbook", "labor_book", "labor"}:
            return "labor"
        return "other"


def _human_name(doc: dict[str, Any]) -> str:
    dtype = str(doc.get("doc_type") or "").strip().lower()
    if dtype in _HUMAN_BY_TYPE:
        return _HUMAN_BY_TYPE[dtype]
    raw = str(doc.get("storage_path") or doc.get("filename") or "файл")
    return Path(raw).stem.replace("_", " ").strip() or "файл"


def build_final_message(documents: list[dict[str, Any]]) -> tuple[str, bool]:
    docs = [d for d in documents if isinstance(d, dict)]
    have = {_bucket(d) for d in docs}
    lines = ["Спасибо! Мы приняли документы:"]
    if docs:
        lines += [f"— {_human_name(d)}" for d in docs]
    else:
        lines.append("— пока файлов в деле нет")
    missing = [code for code in ("ils", "labor") if code not in have]
    if missing:
        need = " и ".join(_MISSING_RU[c] for c in missing)
        lines += [
            "",
            f"Для полного комплекта не хватает: {need}.",
            "Пришлите, пожалуйста, сюда в чат фотографией или файлом.",
        ]
        return "\n".join(lines), False
    lines += [
        "",
        "Комплект полный. Предлагаем приступить к анализу ваших документов.",
        "Мы готовим документы, проект обращения и понятный план — расскажем "
        "по шагам, но обращение через СФР, МФЦ или Госуслуги подаёте вы сами. "
        "Решение о пенсии принимает только СФР.",
    ]
    return "\n".join(lines), True


def final_message_for_case(case_id: str | None) -> tuple[str, bool]:
    cid = str(case_id or "").strip()
    docs: list[dict[str, Any]] = []
    if cid:
        try:
            from sfrfr.db.case_repository import CaseRepository

            docs = list(CaseRepository().list_documents(cid) or [])
        except Exception as exc:  # noqa: BLE001
            logger.debug("final kit list_documents failed: %s", exc)
    return build_final_message(docs)


def analyze_document_background(
    *, case_id: str | None, document_id: str, filename: str, data: bytes
) -> str | None:
    """Фон: определить тип, записать в БД и журнал. Ошибки не роняют приём."""
    try:
        from sfrfr.integrations.max.document_auto_type import guess_from_bytes

        guess = guess_from_bytes(filename=filename, data=data)
        doc_type = str(guess.doc_type or "other").strip().lower()
        if doc_type == "payment_receipt":  # gate #151: обычный файл != чек
            doc_type = "other"
        if doc_type not in CLIENT_LABELS_RU:
            doc_type = "other"
        dtf.set_document_type(document_id=document_id, doc_type=doc_type)
        dtf.append_type_journal(case_id=case_id, filename=filename, doc_type=doc_type)
        return doc_type
    except Exception as exc:  # noqa: BLE001
        logger.warning("background doc analyze failed doc=%s: %s", str(document_id)[:8], exc)
        return None


def schedule_document_background(
    *, case_id: str | None, document_id: str, filename: str, data: bytes
) -> threading.Thread:
    """Запустить разбор после ответа клиенту (не блокируя handler)."""
    thread = threading.Thread(
        target=analyze_document_background,
        kwargs={
            "case_id": case_id,
            "document_id": document_id,
            "filename": filename,
            "data": data,
        },
        name=f"max-doc-bg-{str(document_id)[:8]}",
        daemon=True,
    )
    thread.start()
    return thread
