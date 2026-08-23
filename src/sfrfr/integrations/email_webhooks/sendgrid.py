"""SendGrid Event Webhook: ECDSA по raw body (ТЗ-31b).

Подпись: X-Twilio-Email-Event-Webhook-Signature + Timestamp.
Сообщение для подписи: timestamp + raw_body (байты как есть).
https://www.twilio.com/docs/sendgrid/for-developers/tracking-events/getting-started-event-webhook-security-features

Не использовать распарсенный JSON для verify — только raw bytes.
"""

from __future__ import annotations

import base64
import json
import time
from datetime import UTC, datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_der_public_key, load_pem_public_key

from sfrfr.services.email_delivery_normalize import (
    NormalizedDeliveryEvent,
    classify_bounce,
    event_fingerprint,
    normalize_event_type,
    recipient_domain,
    redact_payload,
)

MAX_CLOCK_SKEW_SECONDS = 300


def _public_key_from_sendgrid(public_key_b64_or_pem: str) -> ec.EllipticCurvePublicKey:
    """SendGrid verification key: base64 DER или PEM."""
    raw = (public_key_b64_or_pem or "").strip()
    if not raw:
        raise ValueError("empty_public_key")
    if "BEGIN PUBLIC KEY" in raw:
        key = load_pem_public_key(raw.encode("utf-8"))
    else:
        key = load_der_public_key(base64.b64decode(raw))
    if not isinstance(key, ec.EllipticCurvePublicKey):
        raise ValueError("not_ec_public_key")
    return key


def verify_sendgrid_signature(
    *,
    public_key: str,
    raw_body: bytes,
    signature_b64: str,
    timestamp: str,
    now: float | None = None,
) -> bool:
    """ECDSA-SHA256(timestamp || raw_body); timestamp ±5 мин."""
    if not public_key or not raw_body or not signature_b64 or not timestamp:
        return False
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    moment = time.time() if now is None else now
    if abs(moment - ts) > MAX_CLOCK_SKEW_SECONDS:
        return False
    try:
        key = _public_key_from_sendgrid(public_key)
        sig = base64.b64decode(signature_b64)
        payload = timestamp.encode("utf-8") + raw_body
        key.verify(sig, payload, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
    except Exception:  # noqa: BLE001
        return False


def parse_sendgrid_payload(raw_body: bytes) -> list[NormalizedDeliveryEvent]:
    """Массив событий SendGrid."""
    try:
        data = json.loads(raw_body.decode("utf-8") or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []

    out: list[NormalizedDeliveryEvent] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        raw_type = str(item.get("event") or "").strip()
        if not raw_type:
            continue
        message_id = str(item.get("sg_message_id") or item.get("smtp-id") or "").strip()
        # sg_message_id часто «id.filter…» — база до «.filter»
        if ".filter" in message_id.casefold():
            message_id = message_id.split(".", 1)[0]
        if not message_id:
            continue

        event_id = str(item.get("sg_event_id") or "").strip() or None
        recipient = str(item.get("email") or "").strip()
        domain = recipient_domain(recipient)

        ts = item.get("timestamp")
        if isinstance(ts, (int, float)):
            occurred = datetime.fromtimestamp(float(ts), tz=UTC)
        else:
            occurred = datetime.now(UTC)

        event_type, severity = normalize_event_type(raw_type)
        bounce_type = None
        error_code = None
        error_category = None

        if raw_type.casefold() in ("bounce", "blocked", "dropped"):
            btype = str(item.get("type") or item.get("bounce_classification") or "").casefold()
            if "soft" in btype:
                bounce_type = "SoftBounce"
            else:
                bounce_type = "HardBounce"
            classified = classify_bounce(
                bounce_type=bounce_type,
                type_code=1 if bounce_type == "HardBounce" else 2,
            )
            event_type = classified
            severity = "error"
            error_category = classified
            error_code = str(item.get("status") or item.get("reason") or "")[:40] or None
        elif raw_type.casefold() in ("spamreport", "group_unsubscribe", "unsubscribe"):
            if "spam" in raw_type.casefold():
                event_type = "complained"
                severity = "error"
                error_category = "spam_complaint"
            else:
                event_type = "unsubscribed"
                severity = "warning"
                error_category = "unsubscribe"
        elif raw_type.casefold() == "processed":
            event_type = "accepted"
            severity = "info"
        elif raw_type.casefold() == "deferred":
            event_type = "deferred"
            severity = "warning"

        safe_raw = {
            "event": raw_type,
            "sg_event_id": event_id,
            "MessageStream": "sendgrid",
            "Type": item.get("type"),
            "status": item.get("status"),
            "reason": str(item.get("reason") or "")[:120],
        }
        fp = event_fingerprint(
            provider="sendgrid",
            provider_event_id=event_id,
            provider_message_id=message_id,
            raw_type=raw_type,
            timestamp=occurred.isoformat(),
        )
        out.append(
            NormalizedDeliveryEvent(
                provider="sendgrid",
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
        )
    return out
