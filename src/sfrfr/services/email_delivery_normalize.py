"""Нормализация и redaction webhook-событий доставки e-mail (ТЗ-31)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sfrfr.core.config import get_settings

# provider raw → (normalized_event_type, severity)
EVENT_MAP: dict[str, tuple[str, str]] = {
    "processed": ("accepted", "info"),
    "accepted": ("accepted", "info"),
    "delivery": ("delivered", "info"),
    "delivered": ("delivered", "info"),
    "deferred": ("deferred", "warning"),
    "temporary_fail": ("deferred", "warning"),
    "bounce": ("bounce", "error"),
    "bounced": ("bounce", "error"),
    "failed": ("failed", "error"),
    "spamcomplaint": ("complained", "error"),
    "spam_complaint": ("complained", "error"),
    "complained": ("complained", "error"),
    "spamreport": ("complained", "error"),
    "subscriptionchange": ("unsubscribed", "warning"),
    "unsubscribed": ("unsubscribed", "warning"),
    "open": ("opened", "info"),
    "opened": ("opened", "info"),
    "click": ("clicked", "info"),
    "clicked": ("clicked", "info"),
}

# Статусы PDF не меняются этими событиями
EMAIL_ONLY_EVENTS = frozenset(
    {
        "accepted",
        "delivered",
        "deferred",
        "bounce",
        "failed",
        "complained",
        "unsubscribed",
        "opened",
        "clicked",
    }
)

_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.I,
)


@dataclass(frozen=True)
class NormalizedDeliveryEvent:
    provider: str
    provider_message_id: str
    provider_event_id: str | None
    raw_type: str
    event_type: str
    severity: str
    occurred_at: datetime
    error_code: str | None
    error_category: str | None
    bounce_type: str | None  # Hard / Soft / None
    recipient_domain: str | None
    payload_redacted: dict[str, Any]
    event_fingerprint: str


def recipient_domain(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return email.rsplit("@", 1)[-1].strip().casefold()[:120] or None


def contact_key_for_email(email: str) -> str:
    """Хеш адреса с серверной солью — не полный e-mail в стоп-листе."""
    settings = get_settings()
    salt = (settings.email_delivery_hash_salt or settings.app_secret_key or "sfrfr").encode(
        "utf-8"
    )
    digest = hashlib.sha256(salt + (email or "").strip().casefold().encode("utf-8")).hexdigest()
    return f"email:{digest[:32]}"


def event_fingerprint(
    *,
    provider: str,
    provider_event_id: str | None,
    provider_message_id: str,
    raw_type: str,
    timestamp: str,
) -> str:
    raw = f"{provider}:{provider_event_id or ''}:{provider_message_id}:{raw_type}:{timestamp}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def redact_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = _EMAIL_RE.sub("[email]", value)
    text = _UUID_RE.sub("[id]", text)
    for marker in ("снилс", "snils", "паспорт", "илс"):
        if marker in text.casefold():
            return "[redacted]"
    return text[:500]


def redact_payload(raw: dict[str, Any], *, recipient_domain_value: str | None) -> dict[str, Any]:
    """Только безопасные поля для журнала."""
    out: dict[str, Any] = {}
    for key in (
        "MessageStream",
        "message_stream",
        "Tag",
        "ServerID",
        "TypeCode",
        "Name",
        "Description",
        "Details",
        "Type",
        "BounceType",
        "CanActivate",
        "Inactive",
        "SuppressSending",
        "Platform",
        "Client",
        "OS",
        "ClickLocation",
    ):
        if key in raw and raw[key] is not None:
            val = raw[key]
            if isinstance(val, str):
                out[key] = redact_text(val)
            elif isinstance(val, (int, float, bool)):
                out[key] = val
    if recipient_domain_value:
        out["recipient_domain"] = recipient_domain_value
    code = raw.get("TypeCode") or raw.get("error_code")
    if code is not None:
        out["response_code"] = str(code)[:40]
    return out


def normalize_event_type(raw: str) -> tuple[str, str]:
    key = (raw or "").strip().casefold().replace(" ", "")
    return EVENT_MAP.get(key, ("unknown", "warning"))


def classify_bounce(*, bounce_type: str | None, type_code: int | None) -> str:
    """Вернуть hard_bounce | soft_bounce."""
    bt = (bounce_type or "").strip().casefold()
    if bt in ("hardbounce", "hard", "permanent"):
        return "hard_bounce"
    if bt in ("softbounce", "soft", "transient"):
        return "soft_bounce"
    # Postmark TypeCode: HardBounce=1, Transient=2, …
    if type_code == 1:
        return "hard_bounce"
    if type_code in (2, 16, 4096):
        return "soft_bounce"
    return "hard_bounce" if bt else "failed"


def parse_iso(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except ValueError:
        return datetime.now(UTC)


def new_event_id() -> str:
    return str(uuid4())
