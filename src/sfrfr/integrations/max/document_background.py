"""Приём документов: один спокойный ответ, тип — фоном, итог после паузы.

Клиенту не спамим одинаковыми ответами на каждое вложение из пачки и не
вешаем howto-кнопки. После паузы — одно уведомление о принятых файлах.
Durable OCR — document_ingest_worker.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from sfrfr.integrations.max import document_type_flow as dtf
from sfrfr.integrations.max.client import inline_buttons_keyboard
from sfrfr.integrations.max.document_auto_type import CLIENT_LABELS_RU

logger = logging.getLogger(__name__)

DONE_PAYLOAD = "max:doc:done"
DONE_LABEL = "Это все документы"
_DONE_TEXTS = {"это всё", "это все", "больше нет", "всё", "все", "готово", "хватит"}

# Пачка вложений: один ack клиенту, итог — после паузы с последнего файла.
_ACK_TTL_SEC = 120.0
_SETTLE_SEC = 45.0
_ack_lock = threading.RLock()
_last_ack_at: dict[str, float] = {}
_quiet_cases: dict[str, float] = {}  # case_id → until (epoch)
_settle_timers: dict[str, threading.Timer] = {}
_user_case: dict[str, str] = {}

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


def processing_ack_text(*, count: int = 1) -> str:
    """Один спокойный ответ на пачку: без howto и без «пришлите следующий»."""
    _ = count  # число файлов не обязательно озвучивать клиенту
    return (
        "Документы получили — спасибо!\n\n"
        "Мне нужно немного времени, чтобы их обработать. "
        "Напишу вам в этот же чат, когда будет готов первичный разбор. "
        "Пока можно просто подождать — отдельно ничего нажимать не нужно."
    )


def saved_text(filename: str, *, count: int = 1) -> str:
    """Совместимость: тот же спокойный ack (имя файла клиенту не нужно)."""
    _ = filename
    return processing_ack_text(count=count)


def reset_quiet_state() -> None:
    with _ack_lock:
        for timer in _settle_timers.values():
            try:
                timer.cancel()
            except Exception:  # noqa: BLE001
                pass
        _last_ack_at.clear()
        _quiet_cases.clear()
        _settle_timers.clear()
        _user_case.clear()


def mark_quiet_ack(user_id: str, *, case_id: str | None) -> None:
    uid = str(user_id or "").strip()
    cid = str(case_id or "").strip()
    now = time.monotonic()
    with _ack_lock:
        if uid:
            _last_ack_at[uid] = now
            if cid:
                _user_case[uid] = cid
        if cid:
            _quiet_cases[cid] = time.time() + _ACK_TTL_SEC


def should_send_processing_ack(user_id: str) -> bool:
    uid = str(user_id or "").strip()
    if not uid:
        return True
    now = time.monotonic()
    with _ack_lock:
        last = _last_ack_at.get(uid)
        if last is not None and now - last < _ACK_TTL_SEC:
            return False
        return True


def is_case_quiet(case_id: str | None) -> bool:
    cid = str(case_id or "").strip()
    if not cid:
        return False
    with _ack_lock:
        until = _quiet_cases.get(cid)
        if until is None:
            return False
        if time.time() > until:
            _quiet_cases.pop(cid, None)
            return False
        return True


def _clear_quiet_case(case_id: str) -> None:
    cid = str(case_id or "").strip()
    with _ack_lock:
        _quiet_cases.pop(cid, None)
        for uid, mapped in list(_user_case.items()):
            if mapped == cid:
                _user_case.pop(uid, None)
                _last_ack_at.pop(uid, None)


def _deliver_settle_notify(*, case_id: str, max_user_id: str) -> None:
    try:
        from sfrfr.services.case_chat_delivery import enqueue_max_delivery

        body, _complete = final_message_for_case(case_id)
        enqueue_max_delivery(
            case_id=case_id,
            message_id=None,
            max_user_id=str(max_user_id),
            body=body,
            attachments=None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("settle notify failed case=%s: %s", str(case_id)[:8], exc)
    finally:
        _clear_quiet_case(case_id)


def schedule_settle_notify(*, user_id: str, case_id: str | None) -> None:
    """После паузы с последнего файла — одно итоговое сообщение клиенту."""
    uid = str(user_id or "").strip()
    cid = str(case_id or "").strip()
    if not uid or not cid:
        return
    with _ack_lock:
        old = _settle_timers.pop(uid, None)
        if old is not None:
            try:
                old.cancel()
            except Exception:  # noqa: BLE001
                pass
        timer = threading.Timer(
            _SETTLE_SEC,
            _deliver_settle_notify,
            kwargs={"case_id": cid, "max_user_id": uid},
        )
        timer.daemon = True
        _settle_timers[uid] = timer
        timer.start()


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
    lines = [
        "Первичный разбор готов.",
        "",
        "Мы приняли документы:",
    ]
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
            "Если они у вас есть — пришлите сюда в чат. "
            "Если нет — напишите, подскажем, как получить.",
        ]
        return "\n".join(lines), False
    lines += [
        "",
        "Комплект полный. Можно приступать к анализу.",
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
