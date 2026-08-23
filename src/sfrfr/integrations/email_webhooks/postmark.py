"""Парсер webhook Postmark → NormalizedDeliveryEvent (ТЗ-31).

Аутентификация: HTTP Basic Auth (официальная схема Postmark; HMAC нет).
Документация: https://postmarkapp.com/developer/webhooks/webhooks-overview
"""

from __future__ import annotations

import base64
import secrets
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


def verify_postmark_basic_auth(
    authorization: str | None,
    *,
    username: str,
    password: str,
) -> bool:
    """Сравнить Authorization: Basic … с ожидаемыми credentials."""
    if not username or not password:
        return False
    header = (authorization or "").strip()
    if not header.lower().startswith("basic "):
        return False
    try:
        decoded = base64.b64decode(header.split(" ", 1)[1].strip()).decode("utf-8")
    except Exception:  # noqa: BLE001
        return False
    if ":" not in decoded:
        return False
    user, pwd = decoded.split(":", 1)
    return secrets.compare_digest(user, username) and secrets.compare_digest(pwd, password)


def parse_postmark_payload(body: dict[str, Any]) -> list[NormalizedDeliveryEvent]:
    """Один JSON-объект Postmark = одно событие (не массив)."""
    record = str(body.get("RecordType") or body.get("record_type") or "").strip()
    if not record:
        return []

    message_id = str(body.get("MessageID") or body.get("MessageId") or "").strip()
    if not message_id:
        return []

    recipient = str(body.get("Recipient") or body.get("Email") or "").strip()
    domain = recipient_domain(recipient)
    occurred_raw = (
        body.get("DeliveredAt")
        or body.get("BouncedAt")
        or body.get("ReceivedAt")
        or body.get("ChangedAt")
        or body.get("ReceivedAt")
    )
    if isinstance(occurred_raw, str):
        occurred = parse_iso(occurred_raw)
    else:
        from datetime import UTC, datetime

        occurred = datetime.now(UTC)

    # Trace id для дедупа, если есть
    event_id = None
    meta = body.get("Metadata") if isinstance(body.get("Metadata"), dict) else {}
    # X-PM-Webhook-Trace-Id приходит в заголовке — передаётся снаружи через body["_trace_id"]
    if body.get("_trace_id"):
        event_id = str(body["_trace_id"])
    elif meta.get("trace_id"):
        event_id = str(meta["trace_id"])

    raw_type = record
    event_type, severity = normalize_event_type(record)
    bounce_type = None
    error_code = None
    error_category = None

    if record.casefold() in ("bounce", "bounced"):
        bounce_type = str(body.get("Type") or body.get("BounceType") or "")
        type_code = body.get("TypeCode")
        code_int = int(type_code) if isinstance(type_code, int) else None
        classified = classify_bounce(bounce_type=bounce_type, type_code=code_int)
        event_type = classified
        severity = "error"
        error_code = str(type_code) if type_code is not None else bounce_type
        error_category = classified
    elif record.casefold() in ("spamcomplaint", "spam_complaint"):
        event_type = "complained"
        severity = "error"
        error_category = "spam_complaint"
    elif record.casefold() == "subscriptionchange":
        suppress = body.get("SuppressSending")
        if suppress is True or str(body.get("SuppressReason") or "").casefold() in (
            "manualsuppression",
            "unsubscribe",
            "hardbounce",
        ):
            event_type = "unsubscribed"
            severity = "warning"
            error_category = "unsubscribe"
        else:
            event_type = "unsubscribed"
            severity = "info"

    fp = event_fingerprint(
        provider="postmark",
        provider_event_id=event_id,
        provider_message_id=message_id,
        raw_type=raw_type,
        timestamp=occurred.isoformat(),
    )

    return [
        NormalizedDeliveryEvent(
            provider="postmark",
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
            payload_redacted=redact_payload(body, recipient_domain_value=domain),
            event_fingerprint=fp,
        )
    ]
