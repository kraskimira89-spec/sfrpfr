"""Очередь bot_reply: идемпотентность, таймаут, fallback специалисту без ПДн в логах."""

from __future__ import annotations

import logging
import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

JOB_STALE_AFTER_SECONDS = 55
MAX_ATTEMPTS = 3
TRANSIENT_MARKERS = ("timeout", "timed out", "429", "500", "502", "503", "504", "connection")
HANDOFF_TEXT = (
    "Сейчас бот не смог подготовить ответ. "
    "Ваше сообщение сохранено и передано специалисту. "
    "Мы ответим в этом же чате."
)


def new_correlation_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


def _log(*, step: str, corr: str, case_id: str = "", job_id: str = "", extra: str = "") -> None:
    logger.info(
        "bot_job step=%s corr=%s case=%s job=%s %s",
        step,
        corr[:36],
        (case_id or "")[:8],
        (job_id or "")[:8],
        extra[:80],
    )


def is_retryable_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in TRANSIENT_MARKERS)


def enqueue_bot_reply_job(
    *,
    case_id: str,
    message_id: str,
    correlation_id: str | None = None,
) -> str | None:
    """Поставить задачу ответа. Повтор с тем же message_id не создаёт вторую задачу."""
    from sfrfr.db.session import get_supabase_client

    cid = (case_id or "").strip()
    mid = (message_id or "").strip()
    corr = (correlation_id or "").strip() or new_correlation_id()
    if not cid or not mid:
        return None
    client = get_supabase_client()
    try:
        existing = (
            client.table("case_chat_bot_jobs")
            .select("id, status")
            .eq("message_id", mid)
            .limit(1)
            .execute()
            .data
            or []
        )
        if existing:
            _log(
                step="enqueue_dup",
                corr=corr,
                case_id=cid,
                job_id=str(existing[0].get("id") or ""),
            )
            return str(existing[0].get("id") or "") or None
        inserted = (
            client.table("case_chat_bot_jobs")
            .insert(
                {
                    "case_id": cid,
                    "message_id": mid,
                    "correlation_id": corr,
                    "status": "queued",
                    "next_retry_at": _now().isoformat(),
                }
            )
            .execute()
            .data
            or []
        )
        job_id = str((inserted[0] or {}).get("id") or "") if inserted else ""
        _log(step="enqueue", corr=corr, case_id=cid, job_id=job_id)
        try:
            from sfrfr.ops.chat_bot_metrics import BOT_JOB_QUEUED

            BOT_JOB_QUEUED.inc()
        except Exception:  # noqa: BLE001
            pass
        return job_id or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("bot_job enqueue failed case=%s: %s", cid[:8], exc)
        return None


def _load_client_text(message_id: str) -> str:
    from sfrfr.db.session import get_supabase_client

    rows = (
        get_supabase_client()
        .table("case_messages")
        .select("body, author_kind")
        .eq("id", message_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return ""
    kind = str(rows[0].get("author_kind") or "")
    if kind not in {"client", "representative"}:
        return ""
    return str(rows[0].get("body") or "").strip()


def _handoff(
    *,
    case: dict[str, Any],
    case_id: str,
    corr: str,
    job_id: str,
    reply_to_message_id: str | None = None,
) -> str | None:
    from sfrfr.services.case_chat_bot import _append_bot_reply

    _log(step="handoff", corr=corr, case_id=case_id, job_id=job_id)
    row = _append_bot_reply(
        case=case,
        case_id=case_id,
        reply=HANDOFF_TEXT,
        reply_to_message_id=reply_to_message_id,
    )
    return str((row or {}).get("id") or "") or None


def _mark(
    job_id: str,
    *,
    status: str,
    attempt_count: int,
    reply_message_id: str | None = None,
    error_category: str | None = None,
    error_code_internal: str | None = None,
    next_retry_at: datetime | None = None,
) -> None:
    from sfrfr.db.session import get_supabase_client

    payload: dict[str, Any] = {
        "status": status,
        "attempt_count": attempt_count,
        "error_category": error_category,
        "error_code_internal": (error_code_internal or "")[:80] or None,
    }
    if status in {"completed", "failed"}:
        payload["finished_at"] = _now().isoformat()
    if status == "processing":
        payload["started_at"] = _now().isoformat()
    if reply_message_id:
        payload["reply_message_id"] = reply_message_id
    if next_retry_at is not None:
        payload["next_retry_at"] = next_retry_at.isoformat()
    get_supabase_client().table("case_chat_bot_jobs").update(payload).eq("id", job_id).execute()


def _due_jobs(*, limit: int) -> list[dict[str, Any]]:
    from sfrfr.db.session import get_supabase_client

    now = _now().isoformat()
    rows = (
        get_supabase_client()
        .table("case_chat_bot_jobs")
        .select("*")
        .in_("status", ["queued", "retrying"])
        .lte("next_retry_at", now)
        .order("created_at")
        .limit(limit)
        .execute()
        .data
        or []
    )
    return [row for row in rows if isinstance(row, dict)]


def process_bot_reply_jobs(*, limit: int = 8) -> int:
    """Взять due-задачи, ответить ботом или передать специалисту."""
    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.case_chat_bot import auto_reply_to_client_message

    done = 0
    for job in _due_jobs(limit=limit):
        job_id = str(job.get("id") or "")
        case_id = str(job.get("case_id") or "")
        message_id = str(job.get("message_id") or "")
        corr = str(job.get("correlation_id") or new_correlation_id())
        attempts = int(job.get("attempt_count") or 0) + 1
        if not job_id or not case_id or not message_id:
            continue
        if job.get("reply_message_id"):
            _mark(job_id, status="completed", attempt_count=attempts)
            done += 1
            continue
        _mark(job_id, status="processing", attempt_count=attempts)
        _log(step="processing", corr=corr, case_id=case_id, job_id=job_id)
        case = CaseRepository().get_case_row(case_id)
        user_text = _load_client_text(message_id)
        if not case or not user_text:
            reply_id = _handoff(
                case=case or {"id": case_id},
                case_id=case_id,
                corr=corr,
                job_id=job_id,
                reply_to_message_id=message_id,
            )
            _mark(
                job_id,
                status="failed",
                attempt_count=attempts,
                reply_message_id=reply_id,
                error_category="missing_case_or_message",
            )
            done += 1
            continue
        try:
            row = auto_reply_to_client_message(
                case=case,
                user_text=user_text,
                reply_to_message_id=message_id,
            )
            reply_id = str((row or {}).get("id") or "") or None
            _mark(job_id, status="completed", attempt_count=attempts, reply_message_id=reply_id)
            _log(step="completed", corr=corr, case_id=case_id, job_id=job_id)
            try:
                from sfrfr.ops.chat_bot_metrics import BOT_JOB_COMPLETED, BOT_REPLY_LATENCY

                BOT_JOB_COMPLETED.inc()
                created = job.get("created_at")
                if isinstance(created, str):
                    from datetime import datetime

                    started = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    BOT_REPLY_LATENCY.observe(max(0.0, (_now() - started).total_seconds()))
            except Exception:  # noqa: BLE001
                pass
            done += 1
        except Exception as exc:  # noqa: BLE001
            retryable = is_retryable_error(exc) and attempts < MAX_ATTEMPTS
            if retryable:
                delay = (2 ** (attempts - 1)) + random.uniform(0, 1)
                nxt = _now() + timedelta(seconds=min(12.0, delay))
                _mark(
                    job_id,
                    status="retrying",
                    attempt_count=attempts,
                    error_category="transient",
                    error_code_internal=type(exc).__name__,
                    next_retry_at=nxt,
                )
                _log(
                    step="retry",
                    corr=corr,
                    case_id=case_id,
                    job_id=job_id,
                    extra=type(exc).__name__,
                )
            else:
                reply_id = _handoff(
                    case=case,
                    case_id=case_id,
                    corr=corr,
                    job_id=job_id,
                    reply_to_message_id=message_id,
                )
                _mark(
                    job_id,
                    status="failed",
                    attempt_count=attempts,
                    reply_message_id=reply_id,
                    error_category="permanent" if not is_retryable_error(exc) else "exhausted",
                    error_code_internal=type(exc).__name__,
                )
                try:
                    from sfrfr.ops.chat_bot_metrics import BOT_JOB_FAILED, LLM_REQUEST_TOTAL

                    category = "permanent" if not is_retryable_error(exc) else "exhausted"
                    BOT_JOB_FAILED.labels(error_category=category).inc()
                    LLM_REQUEST_TOTAL.labels(outcome="error").inc()
                except Exception:  # noqa: BLE001
                    pass
                done += 1
    return done


def expire_stale_bot_jobs() -> int:
    """Задачи старше порога → failed + сообщение «передано специалисту»."""
    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.db.session import get_supabase_client

    cutoff = (_now() - timedelta(seconds=JOB_STALE_AFTER_SECONDS)).isoformat()
    rows = (
        get_supabase_client()
        .table("case_chat_bot_jobs")
        .select("*")
        .in_("status", ["queued", "retrying", "processing"])
        .lt("created_at", cutoff)
        .limit(20)
        .execute()
        .data
        or []
    )
    n = 0
    for job in rows:
        if not isinstance(job, dict) or job.get("reply_message_id"):
            continue
        job_id = str(job.get("id") or "")
        case_id = str(job.get("case_id") or "")
        corr = str(job.get("correlation_id") or new_correlation_id())
        if not job_id or not case_id:
            continue
        case = CaseRepository().get_case_row(case_id) or {"id": case_id}
        message_id = str(job.get("message_id") or "")
        reply_id = _handoff(
            case=case,
            case_id=case_id,
            corr=corr,
            job_id=job_id,
            reply_to_message_id=message_id or None,
        )
        _mark(
            job_id,
            status="failed",
            attempt_count=int(job.get("attempt_count") or 0),
            reply_message_id=reply_id,
            error_category="stale_timeout",
        )
        n += 1
    return n


def process_bot_pipeline(*, limit: int = 8) -> int:
    """Expire + due jobs. Вызывать из worker и background после HTTP 201/200."""
    expired = 0
    processed = 0
    try:
        from sfrfr.db.session import get_supabase_client
        from sfrfr.ops.chat_bot_metrics import refresh_queue_depth

        depth_rows = (
            get_supabase_client()
            .table("case_chat_bot_jobs")
            .select("id")
            .in_("status", ["queued", "retrying", "processing"])
            .limit(500)
            .execute()
            .data
            or []
        )
        refresh_queue_depth(depth=len(depth_rows))
    except Exception as exc:  # noqa: BLE001
        logger.debug("bot_job queue depth skipped: %s", exc)
    try:
        expired = expire_stale_bot_jobs()
    except Exception as exc:  # noqa: BLE001
        logger.warning("bot_job expire skipped: %s", exc)
    try:
        processed = process_bot_reply_jobs(limit=limit)
    except Exception as exc:  # noqa: BLE001
        logger.warning("bot_job process skipped: %s", exc)
    return expired + processed
