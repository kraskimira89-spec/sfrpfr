"""Сервис: создание внутренней задачи Трекера из карточки дела (без ПДн)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status

from sfrfr.core.config import get_settings
from sfrfr.db.session import get_supabase_client
from sfrfr.integrations.yandex_tracker import (
    ISSUE_TYPES,
    build_issue_body,
    case_ref_for,
    create_issue,
    find_pii_violations,
    sanitize_description,
    summary_for_issue,
    tags_for_issue,
    tracker_configured,
    tracker_issue_url,
)

logger = logging.getLogger(__name__)


def find_open_duplicate(*, case_ref: str, issue_type: str) -> dict[str, Any] | None:
    rows = (
        get_supabase_client()
        .table("case_tracker_issues")
        .select("id,tracker_issue_key,tracker_issue_url,issue_type,case_ref,created_at")
        .eq("case_ref", case_ref)
        .eq("issue_type", issue_type)
        .eq("is_open", True)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def list_case_tracker_issues(case_id: str) -> list[dict[str, Any]]:
    rows = (
        get_supabase_client()
        .table("case_tracker_issues")
        .select(
            "id,case_ref,issue_type,tracker_issue_key,tracker_issue_url,"
            "tracker_sync_status,is_open,created_at,direction,source,priority"
        )
        .eq("case_id", case_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
        .data
        or []
    )
    return list(rows)


def create_quality_issue_from_case(
    *,
    case_id: str,
    actor_id: str,
    issue_type: str,
    priority: str,
    direction: str,
    source: str,
    description: str,
    component: str | None = None,
    funnel_stage: str | None = None,
    channel: str | None = None,
    age_bucket: str | None = None,
    repeatability: str | None = None,
    correlation_id: str | None = None,
    title_hint: str | None = None,
    force_new: bool = False,
) -> dict[str, Any]:
    if not tracker_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="tracker_not_configured",
        )
    if issue_type not in ISSUE_TYPES:
        raise HTTPException(status_code=400, detail="invalid_issue_type")

    text = f"{title_hint or ''}\n{description}"
    violations = find_pii_violations(text)
    # UUID в description запрещаем; case_ref генерируем сами
    if violations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "pii_forbidden", "fields": violations},
        )

    case_ref = case_ref_for(case_id)
    if not force_new:
        dup = find_open_duplicate(case_ref=case_ref, issue_type=issue_type)
        if dup:
            return {
                "ok": True,
                "duplicate": True,
                "case_ref": case_ref,
                "tracker_issue_key": dup.get("tracker_issue_key"),
                "tracker_issue_url": dup.get("tracker_issue_url")
                or tracker_issue_url(str(dup.get("tracker_issue_key"))),
                "message": "open_issue_exists",
            }

    safe_desc = sanitize_description(description)
    body = build_issue_body(
        issue_type=issue_type,
        description=safe_desc,
        case_ref=case_ref,
        direction=direction,
        source=source,
        component=component,
        funnel_stage=funnel_stage,
        channel=channel,
        age_bucket=age_bucket,
        repeatability=repeatability,
        correlation_id=correlation_id,
    )
    tags = tags_for_issue(
        issue_type=issue_type,
        direction=direction,
        source=source,
        channel=channel,
        repeatability=repeatability,
    )
    summary = summary_for_issue(issue_type=issue_type, case_ref=case_ref, title_hint=title_hint)

    result = create_issue(summary=summary, description=body, tags=tags, priority=priority)
    if not result.get("ok"):
        _persist_failed(
            case_id=case_id,
            case_ref=case_ref,
            issue_type=issue_type,
            actor_id=actor_id,
            direction=direction,
            source=source,
            priority=priority,
            error=str(result.get("error") or result.get("detail") or "failed")[:300],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "tracker_api_failed",
                "reason": result.get("error"),
                "status_code": result.get("status_code"),
            },
        )

    key = str(result["key"])
    url = str(result.get("url") or tracker_issue_url(key))
    snapshot = {
        "issue_type": issue_type,
        "priority": priority,
        "direction": direction,
        "source": source,
        "component": component,
        "funnel_stage": funnel_stage,
        "channel": channel,
        "age_bucket": age_bucket,
        "repeatability": repeatability,
        "correlation_id": correlation_id,
        "case_ref": case_ref,
        "description_len": len(safe_desc),
    }
    row = {
        "case_id": case_id,
        "case_ref": case_ref,
        "issue_type": issue_type,
        "direction": direction,
        "source": source,
        "priority": priority,
        "tracker_issue_key": key,
        "tracker_issue_url": url,
        "tracker_sync_status": "ok",
        "tracker_sync_error": None,
        "is_open": True,
        "created_by": actor_id if _looks_uuid(actor_id) else None,
        "payload_snapshot": snapshot,
    }
    get_supabase_client().table("case_tracker_issues").insert(row).execute()
    logger.info(
        "tracker_issue_created case_ref=%s type=%s key=%s",
        case_ref,
        issue_type,
        key,
    )
    return {
        "ok": True,
        "duplicate": False,
        "case_ref": case_ref,
        "tracker_issue_key": key,
        "tracker_issue_url": url,
        "payload_preview": snapshot,
    }


def _persist_failed(
    *,
    case_id: str,
    case_ref: str,
    issue_type: str,
    actor_id: str,
    direction: str,
    source: str,
    priority: str,
    error: str,
) -> None:
    try:
        get_supabase_client().table("case_tracker_issues").insert(
            {
                "case_id": case_id,
                "case_ref": case_ref,
                "issue_type": issue_type,
                "direction": direction,
                "source": source,
                "priority": priority,
                "tracker_issue_key": f"FAILED-{case_ref[:8]}-{int(datetime.now(UTC).timestamp())}",
                "tracker_sync_status": "error",
                "tracker_sync_error": error,
                "is_open": False,
                "created_by": actor_id if _looks_uuid(actor_id) else None,
                "payload_snapshot": {"error": error},
            }
        ).execute()
    except Exception:  # noqa: BLE001
        logger.exception("tracker_persist_failed_row")


def _looks_uuid(value: str) -> bool:
    import re

    return bool(
        re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            value,
        )
    )


def recent_auto_incident_exists(*, case_ref: str, issue_type: str, hours: int = 24) -> bool:
    since = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
    rows = (
        get_supabase_client()
        .table("case_tracker_issues")
        .select("id")
        .eq("case_ref", case_ref)
        .eq("issue_type", issue_type)
        .gte("created_at", since)
        .limit(1)
        .execute()
        .data
        or []
    )
    return bool(rows)
