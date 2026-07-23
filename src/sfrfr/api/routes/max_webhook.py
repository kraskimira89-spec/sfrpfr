"""Webhook MAX Bot API."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.handler import handle_max_update

router = APIRouter()

# #region agent log
_DEBUG_LOG = Path("/opt/sfrfr/debug-2e2794.log")


def _agent_log(hypothesis_id: str, location: str, message: str, data: dict[str, Any]) -> None:
    try:
        payload = {
            "sessionId": "2e2794",
            "runId": "pre-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with _DEBUG_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


# #endregion


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
            # #region agent log
            _agent_log(
                "A",
                "max_webhook.py:secret",
                "webhook secret rejected",
                {"has_header": bool(x_max_bot_api_secret)},
            )
            # #endregion
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

    # #region agent log
    sample = updates[0] if updates else {}
    _agent_log(
        "B",
        "max_webhook.py:ingress",
        "webhook received",
        {
            "payload_type": type(payload).__name__,
            "updates_count": len(updates),
            "top_keys": list(sample.keys())[:20] if isinstance(sample, dict) else [],
            "update_type": sample.get("update_type") if isinstance(sample, dict) else None,
            "has_message": bool(isinstance(sample, dict) and sample.get("message")),
            "secret_configured": bool(settings.max_webhook_secret),
            "bot_configured": bool(settings.max_bot_token),
        },
    )
    # #endregion

    results = [handle_max_update(u) for u in updates]
    # #region agent log
    _agent_log(
        "B",
        "max_webhook.py:result",
        "webhook processed",
        {
            "processed": len(results),
            "actions": [r.action for r in results],
            "details": [r.detail for r in results],
            "ok": [r.ok for r in results],
        },
    )
    # #endregion
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
