"""Webhook Яндекс Трекера → inbox (быстрый accept, без бизнес-мутаций)."""

from __future__ import annotations

import logging
import secrets
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status

from sfrfr.core.config import get_settings
from sfrfr.integrations.yandex_tracker.inbox import (
    InMemoryTrackerInboxStore,
    accept_tracker_webhook,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Process-local store до подключения Postgres repository (миграция tracker_sync).
_INBOX = InMemoryTrackerInboxStore()


def _inbox_store() -> InMemoryTrackerInboxStore:
    return _INBOX


@router.post("/integrations/tracker/commands", status_code=status.HTTP_200_OK)
async def tracker_commands_webhook(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Принять сигнал/команду Трекера в inbox.

    Не подтверждает оплату/подачу. Тяжёлая обработка — inbox worker.
    """
    settings = get_settings()
    if not settings.tracker_case_sync_enabled:
        raise HTTPException(status_code=503, detail="tracker_case_sync_disabled")
    expected = (settings.tracker_webhook_secret or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="tracker_webhook_not_configured")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="unauthorized")
    token = authorization.split(" ", 1)[1].strip()
    if not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="unauthorized")

    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid_json") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="invalid_body")

    schema_version = body.get("schema_version")
    if schema_version != 1:
        raise HTTPException(status_code=400, detail="unsupported_schema_version")

    issue_key = str(body.get("issue_key") or "").strip()
    issue_id = str(body.get("issue_id") or issue_key).strip()
    command_id = str(body.get("command_id") or "").strip()
    command_type = str(body.get("command_type") or "signal_reread").strip()
    if not issue_key or not issue_id or not command_id:
        raise HTTPException(status_code=400, detail="missing_required_fields")

    org = (settings.tracker_webhook_organization_id or settings.tracker_org_id or "").strip()
    if not org:
        raise HTTPException(status_code=503, detail="tracker_org_not_configured")

    # Пока нет надёжного source_event_id от автодействия — signal_reread.
    # Необратимые команды с таким сигналом не выполняем в worker.
    if command_type not in {"signal_reread", "request_followup", "record_call_result"}:
        raise HTTPException(status_code=400, detail="unsupported_command_type")

    dedupe_key = f"{org}:{command_id}"
    try:
        result = accept_tracker_webhook(
            _inbox_store(),
            organization_id=org,
            tracker_issue_id=issue_id,
            event_kind=command_type,
            dedupe_key=dedupe_key,
            payload={
                "schema_version": 1,
                "issue_key": issue_key,
                "issue_id": issue_id,
                "command_id": command_id,
                "command_type": command_type,
                "expected_case_revision": body.get("expected_case_revision"),
            },
            source_event_id=command_id,
        )
    except ValueError as exc:
        if "conflict" in str(exc):
            raise HTTPException(status_code=409, detail="payload_conflict") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info(
        "tracker_webhook_accepted issue=%s duplicate=%s",
        issue_key,
        result.duplicate,
    )
    return {
        "ok": True,
        "inbox_id": result.inbox_id,
        "duplicate": result.duplicate,
    }
