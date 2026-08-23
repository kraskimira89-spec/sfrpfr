"""Policy engine: can_contact для сервисных/маркетинговых сообщений (ТЗ-30).

Сервис по активной диагностике ≠ маркетинг (отдельное согласие).
Все проверки — на backend до draft/approve/send.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sfrfr.services.marketing_consent import can_send_marketing

Channel = Literal["max", "email", "sms"]
MessageType = Literal["service", "marketing"]

MSK = ZoneInfo("Europe/Moscow")
QUIET_START_HOUR = 20  # 20:00 local
QUIET_END_HOUR = 9  # до 09:00
MAX_SERVICE_PER_48H = 1
DAYTIME_SEND_HOUR = 10


@dataclass(frozen=True)
class ContactDecision:
    allowed: bool
    reason: str


def is_quiet_hours(now: datetime | None = None, *, tz: ZoneInfo = MSK) -> bool:
    local = (now or datetime.now(UTC)).astimezone(tz)
    return local.hour >= QUIET_START_HOUR or local.hour < QUIET_END_HOUR


def next_daytime_window(after: datetime | None = None, *, tz: ZoneInfo = MSK) -> datetime:
    """Ближайшее окно после quiet hours (10:00 local)."""
    local = (after or datetime.now(UTC)).astimezone(tz)
    if local.hour >= QUIET_START_HOUR:
        local = (local + timedelta(days=1)).replace(
            hour=DAYTIME_SEND_HOUR, minute=0, second=0, microsecond=0
        )
    elif local.hour < QUIET_END_HOUR:
        local = local.replace(hour=DAYTIME_SEND_HOUR, minute=0, second=0, microsecond=0)
    return local.astimezone(UTC)


def looks_like_bot_user_agent(user_agent: str | None) -> bool:
    """Prefetch/сканеры почты — не считать открытием PDF."""
    ua = (user_agent or "").casefold()
    if not ua:
        return False
    markers = (
        "bot",
        "crawler",
        "spider",
        "preview",
        "slackbot",
        "discordbot",
        "whatsapp",
        "telegrambot",
        "facebookexternalhit",
        "outlook",
        "safelinks",
        "proofpoint",
        "barracuda",
        "mime-attachment",
        "python-requests",
        "curl/",
        "wget",
        "headless",
    )
    return any(m in ua for m in markers)


def can_contact(
    *,
    message_type: MessageType,
    channel: Channel,
    do_not_contact: bool = False,
    pd_consent_revoked: bool = False,
    channel_available: bool = True,
    hard_bounce: bool = False,
    case_archived: bool = False,
    active_manual_dialog_48h: bool = False,
    service_messages_last_48h: int = 0,
    marketing_consent_rows: list[dict[str, Any]] | None = None,
) -> ContactDecision:
    """Единая блокировка перед draft/approve/send."""
    if do_not_contact:
        return ContactDecision(False, "do_not_contact")
    if pd_consent_revoked:
        return ContactDecision(False, "pd_consent_revoked")
    if case_archived:
        return ContactDecision(False, "case_archived")
    if not channel_available:
        return ContactDecision(False, "channel_unavailable")
    if hard_bounce:
        return ContactDecision(False, "hard_bounce")
    if active_manual_dialog_48h:
        return ContactDecision(False, "active_manual_dialog")
    if message_type == "service" and service_messages_last_48h >= MAX_SERVICE_PER_48H:
        return ContactDecision(False, "notification_limit_exceeded")
    if message_type == "marketing":
        gate = can_send_marketing(marketing_consent_rows or [], channel=channel)
        if not gate.allowed:
            return ContactDecision(False, gate.reason)
    return ContactDecision(True, "ok")


def idempotency_notification(result_id: str, job_type: str, *, version: str = "v1") -> str:
    return f"result:{result_id}:notification:{job_type}:{version}"


def idempotency_survey(result_id: str, survey_type: str, *, version: str = "v1") -> str:
    return f"result:{result_id}:survey:{survey_type}:{version}"
