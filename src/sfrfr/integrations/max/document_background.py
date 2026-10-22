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
_last_settle_body: dict[str, str] = {}  # case_id → последний текст settle

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
    """Один спокойный ответ на пачку: без howto и без обещания анализа."""
    _ = count  # число файлов не обязательно озвучивать клиенту
    return (
        "Документы получили — спасибо!\n\n"
        "Сверяю комплект с тем, что уже есть в деле. "
        "Напишу сюда, если чего-то не хватает или можно идти дальше. "
        "Пока отдельно ничего нажимать не нужно."
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
        _last_settle_body.clear()


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
    """Проверка без записи (тесты). Для ответа клиенту используйте claim_processing_ack."""
    uid = str(user_id or "").strip()
    if not uid:
        return True
    now = time.monotonic()
    with _ack_lock:
        last = _last_ack_at.get(uid)
        return not (last is not None and now - last < _ACK_TTL_SEC)


def claim_processing_ack(user_id: str, *, case_id: str | None = None) -> bool:
    """Атомарно: один ack на пользователя в окне TTL (без гонки should/mark)."""
    uid = str(user_id or "").strip()
    cid = str(case_id or "").strip()
    now = time.monotonic()
    with _ack_lock:
        last = _last_ack_at.get(uid) if uid else None
        allow = not uid or last is None or now - last >= _ACK_TTL_SEC
        if not allow:
            return False
        if uid:
            _last_ack_at[uid] = now
            if cid:
                _user_case[uid] = cid
        if cid:
            _quiet_cases[cid] = time.time() + _ACK_TTL_SEC
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
        from sfrfr.services.case_chat_context import (
            fetch_recent_case_messages,
            staff_dialog_active,
        )
        from sfrfr.services.case_chat_delivery import enqueue_max_delivery

        history = fetch_recent_case_messages(case_id)
        if staff_dialog_active(history):
            logger.info(
                "settle notify skipped staff_active case=%s", str(case_id)[:8]
            )
            return

        # Перед итогом — добить типы у файлов с null (часто local-pending).
        reclassify_case_untyped(case_id)
        body, complete = final_message_for_case(case_id)
        with _ack_lock:
            prev = _last_settle_body.get(case_id)
            if prev == body:
                logger.info(
                    "settle notify skipped unchanged case=%s", str(case_id)[:8]
                )
                # Комплект уже сообщали — краткий анализ всё равно можно догнать.
                if complete:
                    _schedule_brief_safe(case_id=case_id, max_user_id=max_user_id)
                return
            _last_settle_body[case_id] = body
        enqueue_max_delivery(
            case_id=case_id,
            message_id=None,
            max_user_id=str(max_user_id),
            body=body,
            attachments=None,
        )
        if complete:
            _schedule_brief_safe(case_id=case_id, max_user_id=max_user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("settle notify failed case=%s: %s", str(case_id)[:8], exc)
    finally:
        _clear_quiet_case(case_id)


def _schedule_brief_safe(*, case_id: str, max_user_id: str) -> None:
    try:
        from sfrfr.services.brief_analysis import schedule_brief_after_kit

        schedule_brief_after_kit(case_id=case_id, max_user_id=str(max_user_id))
    except Exception as exc:  # noqa: BLE001
        logger.debug("brief schedule skipped: %s", exc)


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


_NAMELESS_STEMS = frozenset(
    {
        "document",
        "file",
        "scan",
        "скан",
        "файл",
        "документ",
        "image",
        "img",
        "photo",
        "фото",
    }
)


def _human_name(doc: dict[str, Any]) -> str:
    """Строка для списка: «— тип»; безымянные — только тип, без сырого имени файла."""
    dtype = str(doc.get("doc_type") or "").strip().lower()
    label = _HUMAN_BY_TYPE.get(dtype) or CLIENT_LABELS_RU.get(dtype) or "другой документ"
    raw = str(doc.get("filename") or doc.get("storage_path") or "").strip()
    stem = Path(raw).stem.replace("_", " ").strip().lower() if raw else ""
    if not stem or stem in _NAMELESS_STEMS or stem.startswith("document"):
        return label
    # Имя файла совпадает с типом или бесполезно — оставляем тип.
    if label.lower() in stem or stem in label.lower():
        return label
    return label


def _dedupe_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Один файл на checksum (или id); дубликаты перезагрузок не показываем."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    # Свежие сверху — оставляем первый встреченный ключ.
    ordered = sorted(
        documents,
        key=lambda d: str(d.get("created_at") or ""),
        reverse=True,
    )
    for doc in ordered:
        key = str(doc.get("checksum_sha256") or "").strip() or str(doc.get("id") or "").strip()
        if not key:
            key = f"path:{doc.get('storage_path') or doc.get('filename') or id(doc)}"
        if key in seen:
            continue
        seen.add(key)
        out.append(doc)
    out.reverse()
    return out


def build_final_message(documents: list[dict[str, Any]]) -> tuple[str, bool]:
    docs = _dedupe_documents([d for d in documents if isinstance(d, dict)])
    have = {_bucket(d) for d in docs}
    # Не обещаем «разбор» — только учёт комплекта по реестру.
    lines = [
        "Документы получили — сверяем комплект.",
        "",
        "Сейчас в деле:",
    ]
    if docs:
        labels: list[str] = []
        seen_labels: set[str] = set()
        for d in docs:
            name = _human_name(d)
            if name in seen_labels:
                continue
            seen_labels.add(name)
            labels.append(name)
        lines += [f"— {name}" for name in labels]
    else:
        lines.append("— пока файлов в деле нет")
    missing = [code for code in ("ils", "labor") if code not in have]
    if "labor" in have and "ils" in missing:
        lines += [
            "",
            "Трудовую книжку получили, повторно присылать её не нужно. "
            "Содержание ещё проверяем.",
            "Для продолжения нужна выписка о стаже — если вы её ещё не отправляли.",
        ]
        return "\n".join(lines), False
    if "ils" in have and "labor" in missing:
        lines += [
            "",
            "Выписку о стаже получили, повторно присылать её не нужно.",
            "Для продолжения нужна трудовая книжка — если вы её ещё не отправляли.",
        ]
        return "\n".join(lines), False
    if missing:
        need = " и ".join(_MISSING_RU[c] for c in missing)
        lines += [
            "",
            f"Для полного комплекта не хватает: {need}.",
            "Если они у вас есть — пришлите сюда в чат. "
            "Если нет — напишите, подскажем, как получить.",
        ]
        return "\n".join(lines), False
    # Реестр типов полный — краткий разбор стартует отдельно после settle.
    lines += [
        "",
        "Базовый комплект получен. Сейчас выполню краткую предварительную "
        "проверку и напишу сюда результат. "
        "Повторно присылать те же файлы не нужно.",
        "Мы готовим документы и план — обращение через СФР или Госуслуги "
        "подаёте вы сами. Решение о пенсии принимает только СФР.",
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


def _persist_preview(document_id: str, text: str) -> None:
    preview = (text or "").strip()
    if not preview or preview.startswith("[ocr_"):
        return
    try:
        from sfrfr.db.session import get_supabase_client

        get_supabase_client().table("documents").update(
            {"content_preview": preview[:2000]}
        ).eq("id", document_id).execute()
    except Exception as exc:  # noqa: BLE001
        logger.debug("content_preview update skipped: %s", exc)


def analyze_document_background(
    *, case_id: str | None, document_id: str, filename: str, data: bytes
) -> str | None:
    """Определить тип, записать в БД и журнал. Вызывать синхронно при приёме."""
    doc_id = str(document_id or "").strip()
    if not doc_id:
        return None
    doc_type = "other"
    try:
        from sfrfr.integrations.max.document_auto_type import guess_from_bytes
        from sfrfr.ocr.engine import extract_text_from_bytes

        text = ""
        if data:
            try:
                text = extract_text_from_bytes(data, filename) or ""
            except Exception:  # noqa: BLE001
                text = ""
        guess = guess_from_bytes(filename=filename, data=data or b"")
        doc_type = str(guess.doc_type or "other").strip().lower()
        if doc_type == "payment_receipt":  # gate #151: обычный файл != чек
            doc_type = "other"
        if doc_type not in CLIENT_LABELS_RU:
            doc_type = "other"
        ok = dtf.set_document_type(document_id=doc_id, doc_type=doc_type)
        if not ok:
            logger.warning(
                "doc_type not saved doc=%s type=%s", doc_id[:8], doc_type
            )
        _persist_preview(doc_id, text)
        dtf.append_type_journal(
            case_id=case_id,
            filename=filename,
            doc_type=doc_type,
            document_id=doc_id,
        )
        return doc_type
    except Exception as exc:  # noqa: BLE001
        logger.warning("doc analyze failed doc=%s: %s", doc_id[:8], exc)
        try:
            dtf.set_document_type(document_id=doc_id, doc_type="other")
        except Exception:  # noqa: BLE001
            pass
        return "other"


def reclassify_case_untyped(case_id: str | None) -> int:
    """Повторно классифицировать документы дела с пустым doc_type (без клиента)."""
    cid = str(case_id or "").strip()
    if not cid:
        return 0
    try:
        from sfrfr.db.case_repository import CaseRepository
        from sfrfr.storage.local import path_from_uploads_relative
    except Exception:  # noqa: BLE001
        return 0
    updated = 0
    try:
        docs = list(CaseRepository().list_documents(cid) or [])
    except Exception as exc:  # noqa: BLE001
        logger.debug("reclassify list_documents failed: %s", exc)
        return 0
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        if str(doc.get("doc_type") or "").strip():
            continue
        doc_id = str(doc.get("id") or "").strip()
        if not doc_id:
            continue
        local_rel = str(doc.get("local_path") or "").strip()
        storage = str(doc.get("storage_path") or "")
        filename = Path(local_rel or storage).name or "document"
        data = b""
        if local_rel:
            path = path_from_uploads_relative(local_rel)
            if path is not None and path.is_file():
                try:
                    data = path.read_bytes()
                except OSError:
                    data = b""
        if not data:
            # Хотя бы по имени файла (ТК_… → workbook).
            analyze_document_background(
                case_id=cid, document_id=doc_id, filename=filename, data=b""
            )
            updated += 1
            continue
        analyze_document_background(
            case_id=cid, document_id=doc_id, filename=filename, data=data
        )
        updated += 1
    return updated


def schedule_document_background(
    *, case_id: str | None, document_id: str, filename: str, data: bytes
) -> threading.Thread | None:
    """Совместимость: классификация синхронно (тип должен быть до settle)."""
    analyze_document_background(
        case_id=case_id, document_id=document_id, filename=filename, data=data
    )
    return None
