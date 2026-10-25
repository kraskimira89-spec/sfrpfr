"""Пилот проекции 13 ступеней → очередь CASE (allowlist, sync может быть выкл.).

Глобальный TRACKER_CASE_SYNC_ENABLED не включается этим модулем.
Enqueue разрешён только для case_id из TRACKER_CASE_SYNC_ALLOWLIST.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sfrfr.core.config import get_settings
from sfrfr.db.session import get_supabase_client
from sfrfr.db.tracker_outbox_store import PostgresTrackerOutboxStore
from sfrfr.integrations.yandex_tracker.outbox import (
    enqueue_projection_event,
    process_tracker_outbox,
)
from sfrfr.integrations.yandex_tracker.projection import parse_field_ids_json

logger = logging.getLogger(__name__)

def parse_sync_allowlist(raw: str | None = None) -> set[str]:
    text = raw if raw is not None else get_settings().tracker_case_sync_allowlist
    return {p.strip() for p in str(text or "").split(",") if p.strip()}


def is_case_sync_allowlisted(case_id: str) -> bool:
    cid = str(case_id or "").strip()
    if not cid:
        return False
    return cid in parse_sync_allowlist()


def _case_ref(case: dict[str, Any]) -> str:
    return str(case.get("case_number") or case.get("id") or "")[:64]


def _lookup_case_dispatch_key(case_id: str) -> str | None:
    """Ищем сохранённый ключ CASE (issue_type=case_dispatch) в case_tracker_issues."""
    client = get_supabase_client()
    try:
        res = (
            client.table("case_tracker_issues")
            .select("tracker_issue_key")
            .eq("case_id", case_id)
            .eq("issue_type", "case_dispatch")
            .eq("is_open", True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "tracker_dispatch_lookup_failed case=%s err=%s",
            case_id[:8],
            type(exc).__name__,
        )
        return None
    rows = list(res.data or [])
    if not rows:
        return None
    key = str(rows[0].get("tracker_issue_key") or "").strip()
    return key or None


def enqueue_stage_projection(
    *,
    case: dict[str, Any],
    current_stage: str,
    next_action: str = "",
    waiting_on: str = "staff",
    issue_key: str | None = None,
) -> dict[str, Any]:
    """Поставить событие проекции в outbox. Требует allowlist + issue_key (или binding)."""
    case_id = str(case.get("id") or "")
    if not is_case_sync_allowlisted(case_id):
        return {"ok": False, "error": "case_not_in_allowlist"}
    key = (issue_key or "").strip() or (_lookup_case_dispatch_key(case_id) or "")
    if not key:
        return {
            "ok": False,
            "error": "missing_case_issue_key",
            "hint": "Создайте карточку CASE и передайте issue_key или issue_type=case_dispatch",
        }
    revision = int(case.get("updated_revision") or case.get("revision") or 0)
    if revision <= 0:
        # стабильный монотонный суррогат из audit count недоступен — timestamp-seconds
        seed = f"{case_id}:{current_stage}"
        revision = int(uuid.uuid5(uuid.NAMESPACE_URL, seed).int % 10_000_000)
    case_ref = _case_ref(case)
    event_id = f"stage:{case_id}:{current_stage}:{revision}"
    payload = {
        "case_ref": case_ref,
        "case_revision": revision,
        "current_stage": current_stage,
        "next_action": (next_action or "")[:500],
        "waiting_on": waiting_on or "staff",
        "sync_status": "ok",
        "analysis_payment": "unknown",
        "appeals_payment": "unknown",
        "escalation_payment": "unknown",
    }
    store = PostgresTrackerOutboxStore()
    event = enqueue_projection_event(
        store,
        event_id=event_id,
        event_type="project_fields",
        case_ref=case_ref,
        issue_key=key,
        case_revision=revision,
        payload=payload,
        case_id=case_id,
    )
    return {
        "ok": True,
        "event_id": event.event_id,
        "issue_key": key,
        "case_revision": revision,
        "status": event.status,
    }


async def tick_outbox(*, limit: int = 20) -> dict[str, Any]:
    """Обработать pending outbox (нужны credentials + field ids)."""
    settings = get_settings()
    token = (settings.tracker_oauth_token or settings.tracker_token or "").strip()
    org = (settings.tracker_org_id or settings.tracker_cloud_org_id or "").strip()
    if not token or not org:
        return {"ok": False, "error": "tracker_credentials_missing"}
    try:
        field_ids = parse_field_ids_json(settings.tracker_case_field_ids_json)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"field_ids:{type(exc).__name__}"}
    if not field_ids:
        return {"ok": False, "error": "tracker_case_field_ids_empty"}

    from sfrfr.integrations.yandex_tracker.client import TrackerClient

    header = "X-Cloud-Org-ID" if settings.tracker_cloud_org_id else "X-Org-ID"
    org_id = settings.tracker_cloud_org_id or settings.tracker_org_id
    store = PostgresTrackerOutboxStore()
    async with TrackerClient(
        oauth_token=token,
        organization_id=org_id,
        organization_header=header,  # type: ignore[arg-type]
    ) as client:
        stats = await process_tracker_outbox(store, client, field_ids=field_ids, limit=limit)
    return {"ok": True, "stats": stats}
