"""Парсер уведомлений Yandex Cloud Postbox → NormalizedDeliveryEvent (ТЗ-31).

Postbox шлёт SES-подобные JSON в Data Streams; Cloud Function форвардит
на наш HTTPS endpoint. Auth: HTTP Basic (как Postmark) — credentials
задаёт CF / API Gateway.

Документация: https://yandex.cloud/ru/docs/postbox/concepts/notification
"""

from __future__ import annotations

import base64
import json
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
    redact_text,
)


def verify_postbox_basic_auth(
    authorization: str | None,
    *,
    username: str,
    password: str,
) -> bool:
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


def _extract_recipient(body: dict[str, Any]) -> str | None:
    delivery = body.get("delivery")
    if isinstance(delivery, dict):
        recips = delivery.get("recipients")
        if isinstance(recips, list) and recips:
            return str(recips[0] or "").strip() or None
    bounce = body.get("bounce")
    if isinstance(bounce, dict):
        br = bounce.get("bouncedRecipients")
        if isinstance(br, list) and br and isinstance(br[0], dict):
            return str(br[0].get("emailAddress") or "").strip() or None
    complaint = body.get("complaint")
    if isinstance(complaint, dict):
        cr = complaint.get("complainedRecipients")
        if isinstance(cr, list) and cr and isinstance(cr[0], dict):
            return str(cr[0].get("emailAddress") or "").strip() or None
    delay = body.get("deliveryDelay") or body.get("delivery_delay")
    if isinstance(delay, dict):
        dr = delay.get("delayedRecipients")
        if isinstance(dr, list) and dr and isinstance(dr[0], dict):
            return str(dr[0].get("emailAddress") or "").strip() or None
    mail = body.get("mail")
    if isinstance(mail, dict):
        ch = mail.get("commonHeaders")
        if isinstance(ch, dict):
            to_list = ch.get("to")
            if isinstance(to_list, list) and to_list:
                raw = str(to_list[0] or "")
                if "<" in raw and ">" in raw:
                    return raw.split("<", 1)[1].split(">", 1)[0].strip()
                if "@" in raw:
                    return raw.strip()
    return None


def _occurred_at(body: dict[str, Any], event_type: str) -> Any:
    for key in (
        "delivery",
        "bounce",
        "complaint",
        "open",
        "click",
        "deliveryDelay",
        "subscription",
        "failure",
        "send",
    ):
        obj = body.get(key)
        if isinstance(obj, dict) and obj.get("timestamp"):
            return parse_iso(str(obj["timestamp"]))
    mail = body.get("mail")
    if isinstance(mail, dict) and mail.get("timestamp"):
        return parse_iso(str(mail["timestamp"]))
    return parse_iso(None)


def _redact_postbox(body: dict[str, Any], domain: str | None) -> dict[str, Any]:
    out = redact_payload(body, recipient_domain_value=domain)
    out["eventType"] = redact_text(str(body.get("eventType") or "")) or None
    mail = body.get("mail") if isinstance(body.get("mail"), dict) else {}
    if mail.get("messageId"):
        out["mail_messageId"] = str(mail["messageId"])[:80]
    bounce = body.get("bounce") if isinstance(body.get("bounce"), dict) else {}
    if bounce.get("bounceType"):
        out["bounceType"] = str(bounce["bounceType"])[:40]
    if bounce.get("bounceSubType"):
        out["bounceSubType"] = str(bounce["bounceSubType"])[:40]
    failure = body.get("failure") if isinstance(body.get("failure"), dict) else {}
    if failure.get("errorMessage"):
        out["errorMessage"] = redact_text(str(failure["errorMessage"]))
    return {k: v for k, v in out.items() if v is not None}


def parse_postbox_event(body: dict[str, Any]) -> list[NormalizedDeliveryEvent]:
    """Один объект уведомления Postbox."""
    raw_type = str(body.get("eventType") or body.get("event_type") or "").strip()
    if not raw_type:
        return []

    mail = body.get("mail") if isinstance(body.get("mail"), dict) else {}
    message_id = str(mail.get("messageId") or mail.get("message_id") or "").strip()
    if not message_id:
        ch = mail.get("commonHeaders") if isinstance(mail.get("commonHeaders"), dict) else {}
        message_id = str(ch.get("messageId") or "").strip()
    if not message_id:
        return []

    recipient = _extract_recipient(body)
    domain = recipient_domain(recipient)
    occurred = _occurred_at(body, raw_type)
    event_id = str(body.get("eventId") or body.get("event_id") or "").strip() or None

    event_type, severity = normalize_event_type(raw_type)
    bounce_type = None
    error_code = None
    error_category = None

    key = raw_type.casefold().replace(" ", "")
    if key == "send":
        event_type, severity = "accepted", "info"
    elif key == "bounce":
        bounce = body.get("bounce") if isinstance(body.get("bounce"), dict) else {}
        bounce_type = str(bounce.get("bounceType") or "")
        classified = classify_bounce(bounce_type=bounce_type, type_code=None)
        event_type = classified
        severity = "error"
        error_code = bounce_type or None
        error_category = classified
        br = bounce.get("bouncedRecipients")
        if isinstance(br, list) and br and isinstance(br[0], dict):
            status = br[0].get("status")
            if status:
                error_code = str(status)[:40]
    elif key == "renderingfailure":
        event_type, severity = "failed", "error"
        failure = body.get("failure") if isinstance(body.get("failure"), dict) else {}
        error_category = "rendering_failure"
        error_code = redact_text(str(failure.get("errorMessage") or "render"))[:40]
    elif key == "deliverydelay":
        event_type, severity = "deferred", "warning"
        error_category = "delivery_delay"
    elif key == "complaint":
        event_type, severity = "complained", "error"
        error_category = "spam_complaint"
    elif key == "subscription":
        event_type, severity = "unsubscribed", "warning"
        error_category = "unsubscribe"

    fp = event_fingerprint(
        provider="yandex_postbox",
        provider_event_id=event_id,
        provider_message_id=message_id,
        raw_type=raw_type,
        timestamp=occurred.isoformat(),
    )
    return [
        NormalizedDeliveryEvent(
            provider="yandex_postbox",
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
            payload_redacted=_redact_postbox(body, domain),
            event_fingerprint=fp,
        )
    ]


def _decode_yds_data(raw: str) -> dict[str, Any] | None:
    try:
        text = raw
        # иногда base64
        if not raw.strip().startswith("{"):
            text = base64.b64decode(raw).decode("utf-8")
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None


def extract_postbox_events(payload: Any) -> list[dict[str, Any]]:
    """Развернуть CF / YDS обёртки до списка уведомлений."""
    if isinstance(payload, list):
        out: list[dict[str, Any]] = []
        for item in payload:
            out.extend(extract_postbox_events(item))
        return out
    if not isinstance(payload, dict):
        return []

    if payload.get("eventType") or payload.get("event_type"):
        return [payload]

    nested = payload.get("event") or payload.get("notification")
    if isinstance(nested, dict) and (nested.get("eventType") or nested.get("event_type")):
        return [nested]

    messages = payload.get("messages")
    if isinstance(messages, list):
        found: list[dict[str, Any]] = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            details = msg.get("details") if isinstance(msg.get("details"), dict) else msg
            message = details.get("message") if isinstance(details, dict) else None
            data_raw = None
            if isinstance(message, dict):
                data_raw = message.get("data") or message.get("body")
            if data_raw is None and isinstance(details, dict):
                data_raw = details.get("data")
            if isinstance(data_raw, str):
                decoded = _decode_yds_data(data_raw)
                if decoded:
                    found.extend(extract_postbox_events(decoded))
            elif isinstance(data_raw, dict):
                found.extend(extract_postbox_events(data_raw))
        return found

    records = payload.get("Records") or payload.get("records")
    if isinstance(records, list):
        found = []
        for rec in records:
            found.extend(extract_postbox_events(rec))
        return found

    return []


def parse_postbox_payload(payload: Any) -> list[NormalizedDeliveryEvent]:
    events: list[NormalizedDeliveryEvent] = []
    for item in extract_postbox_events(payload):
        events.extend(parse_postbox_event(item))
    return events
