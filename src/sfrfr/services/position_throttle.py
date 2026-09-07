"""Дисклеймер позиции сервиса: не чаще 1 раза на 10 исходящих сообщений бота."""

from __future__ import annotations

import logging
import re

from sfrfr.core.copy import POSITION_SHORT

logger = logging.getLogger(__name__)

POSITION_EVERY_N = 10

_POSITION_MARKERS = re.compile(
    r"(подаёте через\s*сфр|решение принимает\s*сфр|"
    r"не являемся\s*сфр|не гарантир|перерасч[её]т|"
    r"подаёте вы сами|мы не сфр)",
    re.IGNORECASE,
)


def strip_position_phrases(text: str) -> str:
    """Убрать типичные вставки позиции из текста (для throttle)."""
    body = (text or "").strip()
    if not body:
        return body
    # Удаляем целые предложения с маркерами позиции
    parts = re.split(r"(?<=[.!?])\s+", body)
    kept = [p for p in parts if p and not _POSITION_MARKERS.search(p)]
    return " ".join(kept).strip() or body


def count_bot_outbound(*, case_id: str | None) -> int:
    cid = (case_id or "").strip()
    if not cid:
        return 0
    try:
        from sfrfr.db.session import get_supabase_client

        rows = (
            get_supabase_client()
            .table("case_messages")
            .select("id")
            .eq("case_id", cid)
            .eq("author_kind", "system")
            .limit(500)
            .execute()
            .data
            or []
        )
        return len(rows)
    except Exception as exc:  # noqa: BLE001
        logger.debug("count_bot_outbound skipped: %s", exc)
        return 0


def should_include_position(
    *,
    case_id: str | None = None,
    outbound_count: int | None = None,
) -> bool:
    """True примерно для каждого 10-го исходящего сообщения бота (1, 11, 21…)."""
    n = outbound_count if outbound_count is not None else count_bot_outbound(case_id=case_id)
    # Следующее сообщение будет n+1; включаем на 1-м, 11-м, 21-м…
    next_n = n + 1
    return next_n % POSITION_EVERY_N == 1


def maybe_append_position(
    text: str,
    *,
    case_id: str | None = None,
    force: bool = False,
) -> str:
    body = (text or "").strip()
    if not body:
        return body
    if _POSITION_MARKERS.search(body):
        # Уже есть — не дублируем
        return body
    if force or should_include_position(case_id=case_id):
        return f"{body}\n\n{POSITION_SHORT}"
    return body


def apply_position_policy(
    text: str,
    *,
    case_id: str | None = None,
    allow: bool | None = None,
) -> str:
    """Убрать лишние вставки и при необходимости добавить по политике 1/10."""
    cleaned = strip_position_phrases(text)
    include = allow if allow is not None else should_include_position(case_id=case_id)
    if include and not _POSITION_MARKERS.search(cleaned):
        return f"{cleaned}\n\n{POSITION_SHORT}" if cleaned else POSITION_SHORT
    return cleaned
