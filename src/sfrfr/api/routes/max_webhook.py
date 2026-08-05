"""Webhook MAX Bot API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.handler import handle_max_update

router = APIRouter()


@router.post("/webhook")
async def max_webhook(
    request: Request,
    x_max_bot_api_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    """
    Приём апдейтов от MAX.
    Секрет сверяем с MAX_WEBHOOK_SECRET, если он задан.
    """
    settings = get_settings()
    if settings.max_webhook_secret:
        if not x_max_bot_api_secret or x_max_bot_api_secret != settings.max_webhook_secret:
            raise HTTPException(status_code=403, detail="invalid webhook secret")

    payload = await request.json()
    updates: list[dict[str, Any]]
    if isinstance(payload, list):
        updates = [u for u in payload if isinstance(u, dict)]
    elif isinstance(payload, dict):
        if isinstance(payload.get("updates"), list):
            updates = [u for u in payload["updates"] if isinstance(u, dict)]
        else:
            updates = [payload]
    else:
        updates = []

    results = [handle_max_update(u) for u in updates]
    channel_hints = [
        r.detail
        for r in results
        if r.action in {"bot_added", "bot_removed"} and r.detail.startswith("chat_id=")
    ]
    return {
        "ok": True,
        "processed": len(results),
        "actions": [r.action for r in results],
        "case_ids": [r.case_id for r in results if r.case_id],
        "channel_chat_ids": channel_hints,
    }


@router.get("/health")
def max_integration_health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "webhook": f"{settings.public_base_url.rstrip('/')}/api/integrations/max/webhook",
        "bot_configured": "yes" if settings.max_bot_token else "no",
    }


@router.get("/channel-ids")
def max_channel_ids(
    x_ops_token: str | None = Header(default=None, alias="X-Ops-Token"),
    x_max_bot_api_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    """Обнаруженные chat_id каналов на этом сервере (после bot_added)."""
    from sfrfr.integrations.max.channel_ids import list_known, store_path

    settings = get_settings()
    ops = (settings.ops_monitor_token or "").strip()
    secret = (settings.max_webhook_secret or "").strip()
    ok = False
    if ops and x_ops_token == ops:
        ok = True
    if secret and x_max_bot_api_secret == secret:
        ok = True
    if not ok:
        raise HTTPException(status_code=401, detail="ops or webhook secret required")
    return {
        "ok": True,
        "store_path": str(store_path()),
        "max_channel_url": settings.max_channel_url,
        "max_channel_chat_id": settings.max_channel_chat_id or None,
        "discovered": list_known(),
    }
