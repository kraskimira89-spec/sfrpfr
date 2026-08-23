"""HTTPS webhook: доставка e-mail (Postmark MVP, ТЗ-31)."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from sfrfr.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/email/postmark")
async def postmark_email_webhook(
    request: Request,
    authorization: str | None = Header(default=None),
    x_pm_webhook_trace_id: str | None = Header(default=None, alias="X-PM-Webhook-Trace-Id"),
) -> dict[str, Any]:
    """Postmark Delivery/Bounce/Spam/Open/Click/SubscriptionChange.

    Auth: HTTP Basic (POSTMARK_WEBHOOK_USER / POSTMARK_WEBHOOK_PASSWORD).
    Ответ 2xx после устойчивого сохранения события (идемпотентно).
    """
    from sfrfr.integrations.email_webhooks.postmark import (
        parse_postmark_payload,
        verify_postmark_basic_auth,
    )
    from sfrfr.services.email_delivery_webhook import EmailDeliveryWebhookService

    settings = get_settings()
    user = (settings.postmark_webhook_user or "").strip()
    password = (settings.postmark_webhook_password or "").strip()
    if not user or not password:
        raise HTTPException(status_code=503, detail="postmark_webhook_not_configured")

    if not verify_postmark_basic_auth(authorization, username=user, password=password):
        raise HTTPException(status_code=401, detail="Invalid webhook credentials")

    raw = await request.body()
    try:
        body = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid_json") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="expected_object")

    if x_pm_webhook_trace_id:
        body = {**body, "_trace_id": x_pm_webhook_trace_id}

    events = parse_postmark_payload(body)
    if not events:
        # Postmark проверяет endpoint — пустой/тестовый payload → 200
        return {"ok": True, "stored": 0, "note": "no_events"}

    try:
        result = EmailDeliveryWebhookService().process_events(events)
    except Exception as exc:  # noqa: BLE001 — non-2xx → retry провайдера
        logger.exception("postmark webhook processing failed")
        raise HTTPException(status_code=500, detail="processing_failed") from exc

    return result


@router.get("/email/postmark/health")
def postmark_webhook_health() -> dict[str, str]:
    """Проверка маршрута без секретов."""
    configured = bool(
        (get_settings().postmark_webhook_user or "").strip()
        and (get_settings().postmark_webhook_password or "").strip()
    )
    return {"ok": "true", "provider": "postmark", "configured": str(configured).lower()}
