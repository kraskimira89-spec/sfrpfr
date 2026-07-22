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
    return {
        "ok": True,
        "processed": len(results),
        "actions": [r.action for r in results],
        "case_ids": [r.case_id for r in results if r.case_id],
    }


@router.get("/health")
def max_integration_health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "webhook": f"{settings.public_base_url.rstrip('/')}/api/integrations/max/webhook",
        "bot_configured": "yes" if settings.max_bot_token else "no",
    }
