"""Mailgun Event Webhook: HMAC-SHA256(timestamp+token) (ТЗ-31b).

Документация:
https://documentation.mailgun.com/docs/mailgun/user-manual/webhooks/securing-webhooks

Не путать с Postmark Basic Auth или SendGrid ECDSA.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

from sfrfr.services.email_delivery_normalize import (
    NormalizedDeliveryEvent,
    classify_bounce,
    event_fingerprint,
    normalize_event_type,
    parse_iso,
    recipient_domain,
    redact_payload,
)

MAX_CLOCK_SKEW_SECONDS = 300


def verify_mailgun_signature(
    signing_key: str,
    timestamp: str,
    token: str,
    signature: str,
    *,
    now: float | None = None,
) -> bool:
    """HMAC-SHA256 от конкатенации timestamp+token; проверка свежести timestamp."""
    if not signing_key or not timestamp or not token or not signature:
        return False
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    moment = time.time() if now is None else now
    if abs(moment - ts) > MAX_CLOCK_SKEW_SECONDS:
        return False
    expected = hmac.new(
        key=signing_key.encode("utf-8"),
        msg=f"{timestamp}{token}".encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_mailgun_payload(body: dict[str, Any]) -> list[NormalizedDeliveryEvent]:
    """Один JSON Mailgun = одно событие (event-data)."""
    event_data = body.get("event-data")
    if not isinstance(event_data, dict):
        return []

    raw_type = str(event_data.get("event") or "").strip()
    if not raw_type:
        return []

    raw_message = event_data.get("message")
    message: dict[str, Any] = raw_message if isinstance(raw_message, dict) else {}
    raw_headers = message.get("headers")
    headers: dict[str, Any] = raw_headers if isinstance(raw_headers, dict) else {}
    message_id = str(
        headers.get("message-id") or headers.get("Message-Id") or event_data.get("id") or ""
    ).strip()
    if message_id.startswith("<") and message_id.endswith(">"):
        message_id = message_id[1:-1]
    if not message_id:
        return []

    recipient = str(event_data.get("recipient") or "").strip()
    domain = recipient_domain(recipient)

    ts_raw = event_data.get("timestamp")
    if isinstance(ts_raw, (int, float)):
        from datetime import UTC, datetime

        occurred = datetime.fromtimestamp(float(ts_raw), tz=UTC)
    else:
        occurred = parse_iso(str(ts_raw) if ts_raw else None)

    raw_sig = body.get("signature")
    sig_block: dict[str, Any] = raw_sig if isinstance(raw_sig, dict) else {}
    event_id = str(
        event_data.get("id") or sig_block.get("token") or ""
    ).strip() or None

    event_type, severity = normalize_event_type(raw_type)
    bounce_type = None
    error_code = None
    error_category = None

    severity_raw = str(event_data.get("severity") or "").casefold()
    if raw_type.casefold() in ("failed", "bounced", "bounce"):
        # Mailgun: severity permanent → hard, temporary → soft
        if severity_raw == "permanent" or event_data.get("reason") == "bounce":
            bounce_type = "HardBounce"
        elif severity_raw in ("temporary", "transient"):
            bounce_type = "SoftBounce"
        classified = classify_bounce(
            bounce_type=bounce_type,
            type_code=1 if bounce_type == "HardBounce" else 2 if bounce_type else None,
        )
        event_type = classified
        severity = "error"
        error_code = str(event_data.get("delivery-status", {}).get("code") or "")[:40] or None
        if isinstance(event_data.get("delivery-status"), dict):
            code = event_data["delivery-status"].get("code")
            if code is not None:
                error_code = str(code)[:40]
        error_category = classified
    elif raw_type.casefold() in ("complained", "unsubscribed"):
        event_type = "complained" if "complain" in raw_type.casefold() else "unsubscribed"
        severity = "error" if event_type == "complained" else "warning"
        error_category = event_type

    # безопасный redact: без recipient email
    safe_raw = {
        "event": raw_type,
        "severity": event_data.get("severity"),
        "reason": event_data.get("reason"),
        "MessageStream": "mailgun",
    }
    ds = event_data.get("delivery-status")
    if isinstance(ds, dict):
        safe_raw["TypeCode"] = ds.get("code")
        safe_raw["Description"] = str(ds.get("message") or "")[:200]

    fp = event_fingerprint(
        provider="mailgun",
        provider_event_id=event_id,
        provider_message_id=message_id,
        raw_type=raw_type,
        timestamp=occurred.isoformat(),
    )

    return [
        NormalizedDeliveryEvent(
            provider="mailgun",
            provider_message_id=message_id,
            provider_event_id=event_id,
            raw_type=raw_type,
            event_type=event_type,
            severity=severity,
            occurred_at=occurred,
            error_code=error_code,
            error_category=error_category,
            bounce_type=bounce_type,
            recipient_domain=domain,
            payload_redacted=redact_payload(safe_raw, recipient_domain_value=domain),
            event_fingerprint=fp,
        )
    ]
