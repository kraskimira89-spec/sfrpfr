"""Политика маркетинговых vs сервисных сообщений.

Согласие на ПДн ≠ согласие на рекламу.
Сервисные сообщения по активному обращению — отдельно.
Реклама в MAX/email/SMS — только при marketing_consent=granted для канала.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Channel = Literal["max", "email", "sms"]
ConsentStatus = Literal["granted", "denied", "revoked"]
MessageKind = Literal["service", "marketing", "mixed"]

CONSENT_TEXT_VERSION_MAX = "marketing-max-v1"
CONSENT_TEXT_VERSION_EMAIL = "marketing-email-v1"

# Префиксы template_code, которые считаем маркетинговыми (без consent — блок).
MARKETING_TEMPLATE_PREFIXES = (
    "marketing_",
    "promo_",
    "ads_",
    "newsletter_",
)

# Явно сервисные — не требуют marketing consent.
SERVICE_TEMPLATE_PREFIXES = (
    "service_",
    "checklist_",
    "ils_",
    "pay_",
    "cabinet_",
    "docs_",
    "diag_",
)


@dataclass(frozen=True)
class MarketingGateResult:
    allowed: bool
    reason: str
    status: ConsentStatus | None = None
    channel: Channel | None = None


def contact_key_for_max(max_user_id: str) -> str:
    return f"max:{(max_user_id or '').strip()}"


def contact_key_for_email(email: str) -> str:
    return f"email:{(email or '').strip().casefold()}"


def contact_key_for_client(client_id: str) -> str:
    return f"client:{(client_id or '').strip()}"


def classify_template(template_code: str | None, *, kind: MessageKind | None = None) -> MessageKind:
    if kind in ("service", "marketing", "mixed"):
        return kind
    code = (template_code or "").strip().casefold()
    if not code:
        return "service"
    if any(code.startswith(p) for p in MARKETING_TEMPLATE_PREFIXES):
        return "marketing"
    if any(code.startswith(p) for p in SERVICE_TEMPLATE_PREFIXES):
        return "service"
    # Без явной маркировки — не реклама (операторский ответ по делу).
    return "service"


def latest_status(rows: list[dict[str, Any]], *, channel: Channel) -> ConsentStatus | None:
    """Последнее событие по каналу: granted / denied / revoked."""
    for row in rows:
        if str(row.get("channel") or "") != channel:
            continue
        st = str(row.get("status") or "").strip().casefold()
        if st in ("granted", "denied", "revoked"):
            return st  # type: ignore[return-value]
    return None


def can_send_marketing(
    rows: list[dict[str, Any]],
    *,
    channel: Channel,
) -> MarketingGateResult:
    status = latest_status(rows, channel=channel)
    if status == "granted":
        return MarketingGateResult(
            allowed=True,
            reason="marketing_consent_granted",
            status=status,
            channel=channel,
        )
    if status == "revoked":
        return MarketingGateResult(
            allowed=False,
            reason="marketing_consent_revoked",
            status=status,
            channel=channel,
        )
    if status == "denied":
        return MarketingGateResult(
            allowed=False,
            reason="marketing_consent_denied",
            status=status,
            channel=channel,
        )
    return MarketingGateResult(
        allowed=False,
        reason="marketing_consent_missing",
        status=None,
        channel=channel,
    )


def gate_outbound_message(
    rows: list[dict[str, Any]],
    *,
    channel: Channel,
    template_code: str | None = None,
    message_kind: MessageKind | None = None,
) -> MarketingGateResult:
    """Единая проверка перед отправкой.

    service — всегда ок (по каналу обращения).
    mixed — блокируем до явной классификации / согласия.
    marketing — только granted.
    """
    kind = classify_template(template_code, kind=message_kind)
    if kind == "service":
        return MarketingGateResult(
            allowed=True,
            reason="service_message",
            channel=channel,
        )
    if kind == "mixed":
        return MarketingGateResult(
            allowed=False,
            reason="mixed_message_blocked_until_classified",
            channel=channel,
        )
    return can_send_marketing(rows, channel=channel)


def unsubscribe_footer_max() -> str:
    return "Чтобы не получать сообщения, нажмите «Отписаться» или напишите: СТОП."


def is_stop_command(text: str) -> bool:
    t = (text or "").strip().casefold()
    return t in {"стоп", "stop", "отписаться", "unsubscribe", "/stop"}
