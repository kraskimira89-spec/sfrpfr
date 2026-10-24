"""Восстановление staff_document_check_jobs без возврата обработки в HTTP.

Строка в таблице ≠ доказательство выполнения: нужен reclaim + worker poll.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Зависший running без обновления — вернуть в очередь или failed.
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


def reclaim_stale_running_jobs(
    *,
    older_than_sec: int = STALE_RUNNING_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Подхватить «висящие» running после падения процесса.

    attempts < max_attempts → снова queued.
    иначе → failed (не вечный running).
    """
    from sfrfr.db.session import get_supabase_client

    client = get_supabase_client()
    cutoff = (now or datetime.now(UTC)) - timedelta(seconds=max(60, older_than_sec))
    rows = (
        client.table("staff_document_check_jobs")
        .select("id, attempts, max_attempts, locked_at, updated_at, status")
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
        attempts = int(row.get("attempts") or 0)
        max_attempts = int(row.get("max_attempts") or 3)
        if attempts < max_attempts:
            client.table("staff_document_check_jobs").update(
                {
                    "status": "queued",
                    "current_stage": "requeued_stale",
                    "locked_by": None,
                    "locked_at": None,
                    "updated_at": datetime.now(UTC).isoformat(),
                    "last_error": "stale_running_requeued",
                }
            ).eq("id", job_id).eq("status", "running").execute()
            requeued += 1
        else:
            client.table("staff_document_check_jobs").update(
                {
                    "status": "failed",
                    "current_stage": "failed",
                    "finished_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "last_error": "stale_running_exhausted",
                    "locked_by": None,
                    "locked_at": None,
                }
            ).eq("id", job_id).eq("status", "running").execute()
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
