"""Жизненный цикл вложений MAX: без «получили» до байтов в деле.

Durable JSON-store (переживает рестарт процесса на одном VPS).
Стадии: discovered → awaiting_bytes → saved → bound → client_acked | failed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from sfrfr.core.config import get_settings

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
_RETRY_DELAYS_SEC = (15.0, 60.0, 180.0)

CHECKING_TEXT = (
    "Сообщение вижу. Проверяю получение вложений."
)
RESEND_TEXT = (
    "Не удалось получить файл из сообщения. "
    "Пришлите его ещё раз фотографией или документом из телефона."
)

_lock = threading.RLock()
_jobs: dict[str, dict[str, Any]] = {}
_dedupe: dict[str, str] = {}  # dedupe_key → job_id
_checking_sent: dict[str, float] = {}  # user_id → monotonic
_CHECKING_TTL = 120.0
_drain_timer: threading.Timer | None = None


def _store_path() -> Path:
    root = Path(get_settings().storage_local_path).resolve().parent
    return root / "max_attachment_jobs.json"


def reset_for_tests() -> None:
    global _drain_timer
    with _lock:
        if _drain_timer is not None:
            try:
                _drain_timer.cancel()
            except Exception:  # noqa: BLE001
                pass
            _drain_timer = None
        _jobs.clear()
        _dedupe.clear()
        _checking_sent.clear()
        path = _store_path()
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass


def _load() -> None:
    path = _store_path()
    if not path.exists():
        return
    try:
        raw = json.loads(path.read_text(encoding="utf-8") or "{}")
        rows = raw.get("jobs") or {}
        dedupe = raw.get("dedupe") or {}
        if isinstance(rows, dict):
            _jobs.clear()
            for jid, row in rows.items():
                if isinstance(row, dict):
                    _jobs[str(jid)] = row
        if isinstance(dedupe, dict):
            _dedupe.clear()
            for k, v in dedupe.items():
                _dedupe[str(k)] = str(v)
    except Exception:  # noqa: BLE001
        logger.debug("attachment_lifecycle load skipped", exc_info=True)


def _save() -> None:
    path = _store_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"jobs": _jobs, "dedupe": _dedupe}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:  # noqa: BLE001
        logger.debug("attachment_lifecycle save skipped", exc_info=True)


def _ensure_loaded() -> None:
    if not _jobs and not _dedupe:
        _load()


def dedupe_key(*, user_id: str, message_mid: str | None, attach_key: str) -> str:
    raw = f"{user_id}|{message_mid or ''}|{attach_key}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def attach_key_from_parts(
    *,
    token: str | None = None,
    file_id: str | None = None,
    url: str | None = None,
    filename: str | None = None,
    index: int = 0,
) -> str:
    if token:
        digest = hashlib.sha256(str(token).encode("utf-8")).hexdigest()[:16]
        return f"tok:{digest}"
    if file_id:
        digest = hashlib.sha256(str(file_id).encode("utf-8")).hexdigest()[:16]
        return f"fid:{digest}"
    if url:
        digest = hashlib.sha256(str(url).encode("utf-8")).hexdigest()[:16]
        return f"url:{digest}"
    name = (filename or "document").strip() or "document"
    return f"name:{name}:{index}"


def short_attach_id(job_id: str) -> str:
    return str(job_id or "")[:8]


def journal_entry(job: dict[str, Any]) -> dict[str, Any]:
    """Снимок для журнала/логов без URL, token и содержимого файла."""
    return {
        "attach_id": short_attach_id(str(job.get("id") or "")),
        "stage": str(job.get("stage") or ""),
        "error_code": job.get("error_code"),
        "attempts": int(job.get("attempts") or 0),
        "has_file": bool(job.get("document_id")),
        "filename_hint": str(job.get("filename") or "")[:40],
    }


def list_jobs() -> list[dict[str, Any]]:
    with _lock:
        _ensure_loaded()
        return [dict(j) for j in _jobs.values()]


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        _ensure_loaded()
        row = _jobs.get(str(job_id))
        return dict(row) if row else None


def claim_checking_notice(user_id: str) -> bool:
    """Одно «проверяю получение» на пользователя в окне TTL."""
    uid = str(user_id or "").strip()
    if not uid:
        return True
    now = time.monotonic()
    with _lock:
        last = _checking_sent.get(uid)
        if last is not None and now - last < _CHECKING_TTL:
            return False
        _checking_sent[uid] = now
        return True


def enqueue_awaiting_bytes(
    *,
    user_id: str,
    case_id: str | None,
    message_mid: str | None,
    attach_key: str,
    filename: str,
    url: str | None,
    chat_id: int | str | None,
    error_code: str | None = None,
    stage: str = "awaiting_bytes",
) -> dict[str, Any]:
    """Создать или вернуть существующий job по dedupe_key."""
    uid = str(user_id or "").strip()
    key = dedupe_key(user_id=uid, message_mid=message_mid, attach_key=attach_key)
    with _lock:
        _ensure_loaded()
        existing_id = _dedupe.get(key)
        if existing_id and existing_id in _jobs:
            return dict(_jobs[existing_id])
        job_id = str(uuid4())
        now = time.time()
        row: dict[str, Any] = {
            "id": job_id,
            "dedupe_key": key,
            "user_id": uid,
            "case_id": str(case_id or "").strip() or None,
            "message_mid": str(message_mid or "").strip() or None,
            "attach_key": attach_key,
            "filename": str(filename or "document")[:120],
            "url": (str(url).strip() if url else None),
            "chat_id": chat_id,
            "stage": stage,
            "attempts": 0,
            "error_code": error_code,
            "document_id": None,
            "next_attempt_at": now,
            "created_at": now,
            "updated_at": now,
        }
        if stage == "failed" and not error_code:
            row["error_code"] = "unknown"
        if stage == "failed":
            row["next_attempt_at"] = None
        _jobs[job_id] = row
        _dedupe[key] = job_id
        _save()
        logger.info(
            "max_attach_job stage=%s attach_id=%s code=%s",
            row["stage"],
            short_attach_id(job_id),
            row.get("error_code"),
        )
        return dict(row)


def mark_failed(job_id: str, *, error_code: str) -> dict[str, Any] | None:
    with _lock:
        _ensure_loaded()
        row = _jobs.get(str(job_id))
        if not row:
            return None
        row["stage"] = "failed"
        row["error_code"] = error_code
        row["next_attempt_at"] = None
        row["updated_at"] = time.time()
        _save()
        logger.info(
            "max_attach_job stage=failed attach_id=%s code=%s attempts=%s",
            short_attach_id(job_id),
            error_code,
            row.get("attempts"),
        )
        return dict(row)


def mark_attempt_failed(job_id: str, *, error_code: str) -> dict[str, Any]:
    """Увеличить attempts; при исчерпании — failed, иначе awaiting с delay."""
    with _lock:
        _ensure_loaded()
        row = _jobs.get(str(job_id))
        if not row:
            raise KeyError(job_id)
        attempts = int(row.get("attempts") or 0) + 1
        row["attempts"] = attempts
        row["error_code"] = error_code
        row["updated_at"] = time.time()
        if attempts >= MAX_ATTEMPTS:
            row["stage"] = "failed"
            row["next_attempt_at"] = None
        else:
            row["stage"] = "awaiting_bytes"
            delay = _RETRY_DELAYS_SEC[min(attempts - 1, len(_RETRY_DELAYS_SEC) - 1)]
            row["next_attempt_at"] = time.time() + delay
        _save()
        return dict(row)


def mark_bound(
    job_id: str,
    *,
    document_id: str,
    case_id: str | None = None,
) -> dict[str, Any] | None:
    with _lock:
        _ensure_loaded()
        row = _jobs.get(str(job_id))
        if not row:
            return None
        row["stage"] = "bound"
        row["document_id"] = str(document_id)
        if case_id:
            row["case_id"] = str(case_id)
        row["error_code"] = None
        row["next_attempt_at"] = None
        row["updated_at"] = time.time()
        _save()
        return dict(row)


def mark_client_acked(job_id: str) -> dict[str, Any] | None:
    with _lock:
        _ensure_loaded()
        row = _jobs.get(str(job_id))
        if not row:
            return None
        row["stage"] = "client_acked"
        row["updated_at"] = time.time()
        _save()
        return dict(row)


def due_jobs(*, now: float | None = None) -> list[dict[str, Any]]:
    ts = time.time() if now is None else now
    with _lock:
        _ensure_loaded()
        out: list[dict[str, Any]] = []
        for row in _jobs.values():
            if row.get("stage") != "awaiting_bytes":
                continue
            nxt = row.get("next_attempt_at")
            if nxt is None or float(nxt) <= ts:
                out.append(dict(row))
        return out


def document_is_staff_openable(row: dict[str, Any] | None) -> bool:
    """Файл доступен специалисту из карточки (Storage или local_path на диске)."""
    if not row or not str(row.get("id") or "").strip():
        return False
    from sfrfr.services.document_upload import is_document_downloadable
    from sfrfr.storage.local import path_from_uploads_relative

    local_rel = str(row.get("local_path") or "").strip()
    if local_rel:
        path = path_from_uploads_relative(local_rel)
        if path is not None and path.is_file():
            return True
    if str(row.get("cloud_status") or "") == "pending":
        return False
    return is_document_downloadable(
        row, allow_local_pending=True, allow_staff_preview=True
    )


def schedule_drain(*, delay_sec: float = 15.0) -> None:
    """Запланировать фоновый drain due-jobs (один timer)."""
    global _drain_timer

    def _run() -> None:
        global _drain_timer
        try:
            drain_due_jobs()
        except Exception:  # noqa: BLE001
            logger.exception("attachment_lifecycle drain failed")
        finally:
            with _lock:
                _drain_timer = None
            # перепланировать, если остались awaiting
            if due_jobs():
                schedule_drain(delay_sec=15.0)

    with _lock:
        if _drain_timer is not None:
            return
        timer = threading.Timer(max(1.0, float(delay_sec)), _run)
        timer.daemon = True
        _drain_timer = timer
        timer.start()


def drain_due_jobs() -> int:
    """Повторить скачивание due-jobs. Возвращает число обработанных."""
    from sfrfr.integrations.max.attachments import download_file
    from sfrfr.integrations.max.client import MaxBotClient

    processed = 0
    for job in due_jobs():
        processed += 1
        jid = str(job["id"])
        url = job.get("url")
        mid = job.get("message_mid")
        try:
            if not url and mid:
                bot = MaxBotClient()
                refreshed = bot.get_message(str(mid))
                url = _url_from_message_payload(refreshed)
                if url:
                    with _lock:
                        _ensure_loaded()
                        row = _jobs.get(jid)
                        if row:
                            row["url"] = url
                            _save()
            if not url:
                mark_failed(jid, error_code="no_download_mechanism")
                _notify_resend(job)
                continue
            data = download_file(str(url))
            _complete_download(job, data=data)
        except Exception as exc:  # noqa: BLE001
            updated = mark_attempt_failed(jid, error_code=type(exc).__name__)
            if updated.get("stage") == "failed":
                _notify_resend(updated)
    return processed


def _url_from_message_payload(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    from sfrfr.integrations.max.attachments import extract_downloadable_files

    files = extract_downloadable_files(payload)
    if files:
        return files[0][1]
    # иногда API отдаёт message обёртку
    msg = payload.get("message") if isinstance(payload.get("message"), dict) else payload
    if isinstance(msg, dict):
        files = extract_downloadable_files({"message": msg})
        if files:
            return files[0][1]
    return None


def _complete_download(job: dict[str, Any], *, data: bytes) -> None:
    from sfrfr.integrations.max import document_background
    from sfrfr.integrations.max.case_chat_log import (
        append_case_chat_message,
        format_document_event,
    )
    from sfrfr.services.max_document_upload import upload_max_document

    case_id = str(job.get("case_id") or "").strip()
    user_id = str(job.get("user_id") or "")
    filename = str(job.get("filename") or "document")
    jid = str(job["id"])
    if not case_id:
        mark_failed(jid, error_code="no_case")
        _notify_resend(job)
        return
    row = upload_max_document(
        case_id=case_id,
        filename=filename,
        data=data,
        uploaded_by=None,
    )
    if row is None or not str(row.get("id") or "").strip():
        updated = mark_attempt_failed(jid, error_code="ingest_failed")
        if updated.get("stage") == "failed":
            _notify_resend(updated)
        return
    if not document_is_staff_openable(row):
        updated = mark_attempt_failed(jid, error_code="not_staff_openable")
        if updated.get("stage") == "failed":
            _notify_resend(updated)
        return
    doc_id = str(row["id"])
    mark_bound(jid, document_id=doc_id, case_id=case_id)
    try:
        cloud_pending = str(row.get("cloud_status") or "") == "pending"
        body = format_document_event(
            filename=filename,
            document_id=doc_id,
            note="[нужна догрузка в облако]" if cloud_pending else None,
        )
        append_case_chat_message(
            case_id=case_id,
            author_kind="client",
            body=body,
            channel_origin="max",
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        document_background.schedule_document_background(
            case_id=case_id,
            document_id=doc_id,
            filename=filename,
            data=data,
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        document_background.schedule_settle_notify(user_id=user_id, case_id=case_id)
    except Exception:  # noqa: BLE001
        pass
    _notify_got_documents(job, case_id=case_id)


def _notify_resend(job: dict[str, Any]) -> None:
    try:
        from sfrfr.integrations.max.client import MaxBotClient
        from sfrfr.integrations.max.handler import _reply

        bot = MaxBotClient()
        _reply(
            bot,
            user_id=str(job.get("user_id") or ""),
            chat_id=job.get("chat_id"),
            text=RESEND_TEXT,
            case_id=job.get("case_id"),
        )
    except Exception:  # noqa: BLE001
        logger.warning("attach resend notify failed", exc_info=True)


def _notify_got_documents(job: dict[str, Any], *, case_id: str) -> None:
    try:
        from sfrfr.integrations.max import document_background
        from sfrfr.integrations.max.client import MaxBotClient
        from sfrfr.integrations.max.handler import _reply

        uid = str(job.get("user_id") or "")
        if not document_background.claim_processing_ack(uid, case_id=case_id):
            mark_client_acked(str(job["id"]))
            return
        bot = MaxBotClient()
        reply = document_background.processing_ack_text()
        _reply(
            bot,
            user_id=uid,
            chat_id=job.get("chat_id"),
            text=reply,
            case_id=case_id,
        )
        mark_client_acked(str(job["id"]))
    except Exception:  # noqa: BLE001
        logger.warning("attach got-docs notify failed", exc_info=True)
