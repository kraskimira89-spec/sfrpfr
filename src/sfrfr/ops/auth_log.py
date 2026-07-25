"""Структурированные события входа/регистрации портала без ПДн."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("sfrfr.auth.portal")


def _ticket_prefix(ticket: str | None) -> str:
    value = (ticket or "").strip()
    if len(value) <= 8:
        return value or "-"
    return f"{value[:8]}…"


def auth_event(
    event: str,
    *,
    outcome: str,
    audience: str = "client",
    status_code: int | None = None,
    detail: str | None = None,
    ticket: str | None = None,
    max_user_id: str | None = None,
    **extra: Any,
) -> None:
    """Пишет одно событие auth. Не передавать телефон/email/ФИО/токены."""
    parts = [
        f"event={event}",
        f"outcome={outcome}",
        f"audience={audience}",
    ]
    if status_code is not None:
        parts.append(f"status={status_code}")
    if detail:
        # detail уже продуктовый текст без секретов; обрезаем длину
        clean = " ".join(str(detail).split())
        parts.append(f"detail={clean[:160]}")
    if ticket:
        parts.append(f"ticket={_ticket_prefix(ticket)}")
    if max_user_id:
        parts.append(f"max_user_id={max_user_id}")
    for key, value in extra.items():
        if value is None or value == "":
            continue
        parts.append(f"{key}={value}")
    message = " ".join(parts)
    if outcome in {"error", "denied", "fail"}:
        logger.warning(message)
    else:
        logger.info(message)
