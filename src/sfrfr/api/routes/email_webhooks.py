"""HTTPS webhooks доставки e-mail: Postbox / Postmark / Mailgun / SendGrid (ТЗ-31).

Схемы подписи разные — не смешивать алгоритмы.
Канон РФ: Yandex Cloud Postbox (CF → Basic Auth → этот API).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from sfrfr.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_BODY_BYTES = 1_048_576  # 1 MiB


def _reject_oversized(raw: bytes) -> None:
    if len(raw) > _MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="payload_too_large")


@router.post("/email/postbox")
async def postbox_email_webhook(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Yandex Cloud Postbox: JSON уведомлений (напрямую или обёртка YDS/CF)."""
    from sfrfr.integrations.email_webhooks.postbox import (
        parse_postbox_payload,
        verify_postbox_basic_auth,
    )
    from sfrfr.services.email_delivery_webhook import EmailDeliveryWebhookService

    settings = get_settings()
    user = (settings.postbox_webhook_user or "").strip()
    password = (settings.postbox_webhook_password or "").strip()
    if not user or not password:
        raise HTTPException(status_code=503, detail="postbox_webhook_not_configured")

    if not verify_postbox_basic_auth(authorization, username=user, password=password):
        raise HTTPException(status_code=401, detail="Invalid webhook credentials")

    raw = await request.body()
    _reject_oversized(raw)
    try:
        body = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid_json") from exc

    events = parse_postbox_payload(body)
    if not events:
        return {"ok": True, "stored": 0, "note": "no_events"}

    try:
        return EmailDeliveryWebhookService().process_events(events)
    except Exception as exc:  # noqa: BLE001
        logger.exception("postbox webhook processing failed")
        raise HTTPException(status_code=500, detail="processing_failed") from exc


@router.post("/email/postmark")
async def postmark_email_webhook(
    request: Request,
    authorization: str | None = Header(default=None),
    x_pm_webhook_trace_id: str | None = Header(default=None, alias="X-PM-Webhook-Trace-Id"),
) -> dict[str, Any]:
    """Postmark: HTTP Basic Auth (без HMAC)."""
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
    _reject_oversized(raw)
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
        return {"ok": True, "stored": 0, "note": "no_events"}

    try:
        return EmailDeliveryWebhookService().process_events(events)
    except Exception as exc:  # noqa: BLE001
        logger.exception("postmark webhook processing failed")
        raise HTTPException(status_code=500, detail="processing_failed") from exc


@router.post("/email/mailgun")
async def mailgun_email_webhook(request: Request) -> dict[str, Any]:
    """Mailgun: HMAC-SHA256(timestamp+token) + freshness + replay via fingerprint."""
    from sfrfr.integrations.email_webhooks.mailgun import (
        parse_mailgun_payload,
        verify_mailgun_signature,
    )
    from sfrfr.services.email_delivery_webhook import EmailDeliveryWebhookService

    settings = get_settings()
    signing_key = (settings.mailgun_webhook_signing_key or "").strip()
    if not signing_key:
        raise HTTPException(status_code=503, detail="mailgun_webhook_not_configured")

    raw = await request.body()
    _reject_oversized(raw)
    try:
        body = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid_json") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="expected_object")

    raw_sig = body.get("signature")
    sig: dict[str, Any] = raw_sig if isinstance(raw_sig, dict) else {}
    timestamp = str(sig.get("timestamp") or "")
    token = str(sig.get("token") or "")
    signature = str(sig.get("signature") or "")
    if not timestamp or not token or not signature:
        raise HTTPException(status_code=400, detail="Missing Mailgun signature")

    if not verify_mailgun_signature(signing_key, timestamp, token, signature):
        raise HTTPException(status_code=401, detail="Invalid Mailgun signature")

    events = parse_mailgun_payload(body)
    if not events:
        return {"ok": True, "stored": 0, "note": "no_events"}

    try:
        result = EmailDeliveryWebhookService().process_events(events)
    except Exception as exc:  # noqa: BLE001
        logger.exception("mailgun webhook processing failed")
        raise HTTPException(status_code=500, detail="processing_failed") from exc

    # duplicate token → fingerprint hit → duplicates>0, всё равно 200 (идемпотентность)
    return result


@router.post("/email/sendgrid")
async def sendgrid_email_webhook(
    request: Request,
    x_twilio_email_event_webhook_signature: str | None = Header(
        default=None, alias="X-Twilio-Email-Event-Webhook-Signature"
    ),
    x_twilio_email_event_webhook_timestamp: str | None = Header(
        default=None, alias="X-Twilio-Email-Event-Webhook-Timestamp"
    ),
) -> dict[str, Any]:
    """SendGrid: ECDSA по сырым байтам тела (не по распарсенному JSON)."""
    from sfrfr.integrations.email_webhooks.sendgrid import (
        parse_sendgrid_payload,
        verify_sendgrid_signature,
    )
    from sfrfr.services.email_delivery_webhook import EmailDeliveryWebhookService

    settings = get_settings()
    public_key = (settings.sendgrid_event_webhook_public_key or "").strip()
    if not public_key:
        raise HTTPException(status_code=503, detail="sendgrid_webhook_not_configured")

    raw = await request.body()
    _reject_oversized(raw)

    if not x_twilio_email_event_webhook_signature or not x_twilio_email_event_webhook_timestamp:
        raise HTTPException(status_code=400, detail="Missing signature headers")

    if not verify_sendgrid_signature(
        public_key=public_key,
        raw_body=raw,
        signature_b64=x_twilio_email_event_webhook_signature,
        timestamp=x_twilio_email_event_webhook_timestamp,
    ):
        raise HTTPException(status_code=401, detail="Invalid SendGrid signature")

    events = parse_sendgrid_payload(raw)
    if not events:
        return {"ok": True, "stored": 0, "note": "no_events"}

    try:
        return EmailDeliveryWebhookService().process_events(events)
    except Exception as exc:  # noqa: BLE001
        logger.exception("sendgrid webhook processing failed")
        raise HTTPException(status_code=500, detail="processing_failed") from exc


@router.get("/email/health")
def email_webhooks_health() -> dict[str, Any]:
    """Какие провайдеры настроены (без секретов)."""
    from sfrfr.integrations.yandex_postbox import postbox_configured

    s = get_settings()
    return {
        "ok": True,
        "providers": {
            "yandex_postbox": bool(
                (s.postbox_webhook_user or "").strip()
                and (s.postbox_webhook_password or "").strip()
            ),
            "yandex_postbox_send": postbox_configured(),
            "postmark": bool(
                (s.postmark_webhook_user or "").strip()
                and (s.postmark_webhook_password or "").strip()
            ),
            "mailgun": bool((s.mailgun_webhook_signing_key or "").strip()),
            "sendgrid": bool((s.sendgrid_event_webhook_public_key or "").strip()),
        },
    }


@router.get("/email/postmark/health")
def postmark_webhook_health() -> dict[str, str]:
    configured = bool(
        (get_settings().postmark_webhook_user or "").strip()
        and (get_settings().postmark_webhook_password or "").strip()
    )
    return {"ok": "true", "provider": "postmark", "configured": str(configured).lower()}
