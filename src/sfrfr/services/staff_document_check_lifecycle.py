"""Восстановление staff_document_check_jobs без возврата обработки в HTTP.

Строка в таблице ≠ доказательство выполнения: нужен reclaim + worker poll.
Claim только из queued; finalize только владельцем lease; heartbeat продлевает locked_at.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Зависший running без heartbeat — вернуть в очередь или failed.
STALE_RUNNING_SECONDS = 15 * 60


def _parse_ts(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def claim_queued_job(
    client: Any,
    *,
    job_id: str,
    worker_id: str,
    attempts: int,
) -> dict[str, Any] | None:
    """Атомарный claim: только status=queued → running + locked_by.

    Два обработчика одного id: побеждает один (CAS по status).
    """
    rows = (
        client.table("staff_document_check_jobs")
        .update(
            {
                "status": "running",
                "attempts": attempts,
                "current_stage": "extract_classify_kit",
                "locked_by": worker_id,
                "locked_at": _now_iso(),
                "updated_at": _now_iso(),
            }
        )
        .eq("id", job_id)
        .eq("status", "queued")
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def heartbeat_job_lease(
    client: Any,
    *,
    job_id: str,
    worker_id: str,
) -> bool:
    """Продлить lease; True если мы всё ещё владелец running."""
    rows = (
        client.table("staff_document_check_jobs")
        .update({"locked_at": _now_iso(), "updated_at": _now_iso()})
        .eq("id", job_id)
        .eq("status", "running")
        .eq("locked_by", worker_id)
        .execute()
        .data
        or []
    )
    return bool(rows)


def finalize_job_as_owner(
    client: Any,
    *,
    job_id: str,
    worker_id: str,
    payload: dict[str, Any],
) -> bool:
    """Записать результат только если lease всё ещё наш.

    Старый исполнитель после reclaim не перезапишет нового владельца.
    """
    rows = (
        client.table("staff_document_check_jobs")
        .update(payload)
        .eq("id", job_id)
        .eq("status", "running")
        .eq("locked_by", worker_id)
        .execute()
        .data
        or []
    )
    return bool(rows)


def reclaim_stale_running_jobs(
    *,
    older_than_sec: int = STALE_RUNNING_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Подхватить «висящие» running после падения процесса.

    Активный heartbeat (свежий locked_at) → reclaim не трогает.
    attempts < max_attempts → снова queued.
    иначе → failed (не вечный running).
    """
    from sfrfr.db.session import get_supabase_client

    client = get_supabase_client()
    cutoff = (now or datetime.now(UTC)) - timedelta(seconds=max(60, older_than_sec))
    rows = (
        client.table("staff_document_check_jobs")
        .select("id, attempts, max_attempts, locked_at, locked_by, updated_at, status")
        .eq("status", "running")
        .limit(50)
        .execute()
        .data
        or []
    )
    requeued = 0
    failed = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        locked = _parse_ts(row.get("locked_at")) or _parse_ts(row.get("updated_at"))
        if locked is None or locked > cutoff:
            continue
        job_id = str(row.get("id") or "")
        if not job_id:
            continue
        prev_owner = str(row.get("locked_by") or "")
        attempts = int(row.get("attempts") or 0)
        max_attempts = int(row.get("max_attempts") or 3)
        if attempts < max_attempts:
            payload = {
                "status": "queued",
                "current_stage": "requeued_stale",
                "locked_by": None,
                "locked_at": None,
                "updated_at": _now_iso(),
                "last_error": "stale_running_requeued",
            }
        else:
            payload = {
                "status": "failed",
                "current_stage": "failed",
                "finished_at": _now_iso(),
                "updated_at": _now_iso(),
                "last_error": "stale_running_exhausted",
                "locked_by": None,
                "locked_at": None,
            }
        # CAS: running + тот же owner (если был), чтобы не сбить свежий claim.
        upd = (
            client.table("staff_document_check_jobs")
            .update(payload)
            .eq("id", job_id)
            .eq("status", "running")
        )
        if prev_owner:
            upd = upd.eq("locked_by", prev_owner)
        changed = upd.execute().data or []
        if not changed:
            continue
        if attempts < max_attempts:
            requeued += 1
        else:
            failed += 1
    if requeued or failed:
        logger.info(
            "staff_docs_check reclaim requeued=%s failed=%s", requeued, failed
        )
    return {"requeued": requeued, "failed": failed}


def result_already_finalized(job: dict[str, Any]) -> bool:
    status = str(job.get("status") or "")
    if status in {"completed", "needs_action"}:
        return True
    result = job.get("result")
    return isinstance(result, dict) and bool(result.get("primary_precheck"))


def notify_already_recorded(job_or_result: dict[str, Any]) -> bool:
    result = job_or_result.get("result") if "result" in job_or_result else job_or_result
    if not isinstance(result, dict):
        return False
    notify = result.get("client_notify")
    return isinstance(notify, dict) and (
        bool(notify.get("ok"))
        or bool(notify.get("skipped"))
        or bool(notify.get("message_id"))
    )
