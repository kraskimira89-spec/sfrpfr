"""Спокойный ритм напоминания о подаче и решении СФР (уточнение владельца к ТЗ-35).

Ритм: первое после 4 логических сообщений бота; следующее ещё через 8;
далее ещё через 12; дальше интервал 12.
Счётчик устойчивый к перезапуску процесса; техразбиение одного ответа не ускоряет.
"""

from __future__ import annotations

import re
from typing import Any

from sfrfr.integrations.max.intake import MaxIntakeRecord, get_intake_store

# Пороги: накопленный прирост логических сообщений с прошлого напоминания.
NUDGE_INTERVALS: tuple[int, ...] = (4, 8, 12)
NUDGE_INTERVAL_AFTER: int = 12

SHORT_DISCLAIMER = (
    "Мы готовим документы, проект обращения и план — расскажем по шагам, "
    "но подаёте через СФР или Госуслуги вы сами. Решение принимает СФР."
)

_DIRECT_QUESTION_RE = re.compile(
    r"(гарант|перерасч[её]т|вы\s+пода(дите|ёте)|пода(дите|ёте)\s+за\s+меня|"
    r"решени[ея]\s+сфр|сфр\s+решит|обещаете|гарантируете)",
    re.IGNORECASE,
)


def is_direct_submission_question(text: str) -> bool:
    return bool(_DIRECT_QUESTION_RE.search(text or ""))


def next_interval(tier: int) -> int:
    """Сколько ещё логических сообщений до следующего напоминания."""
    if tier < 0:
        tier = 0
    if tier < len(NUDGE_INTERVALS):
        return NUDGE_INTERVALS[tier]
    return NUDGE_INTERVAL_AFTER


def should_nudge(rec: MaxIntakeRecord) -> bool:
    since = int(rec.logical_bot_msg_count or 0) - int(rec.submission_nudge_at_count or 0)
    return since >= next_interval(int(rec.submission_nudge_tier or 0))


def note_logical_bot_message(rec: MaxIntakeRecord, *, count: int = 1) -> MaxIntakeRecord:
    """Учесть одно логическое сообщение бота (не техчасть и не ack файла)."""
    rec.logical_bot_msg_count = int(rec.logical_bot_msg_count or 0) + max(1, int(count))
    get_intake_store().save(rec)
    return rec


def mark_nudged(rec: MaxIntakeRecord) -> MaxIntakeRecord:
    rec.submission_nudge_tier = int(rec.submission_nudge_tier or 0) + 1
    rec.submission_nudge_at_count = int(rec.logical_bot_msg_count or 0)
    get_intake_store().save(rec)
    return rec


def maybe_append_disclaimer(rec: MaxIntakeRecord, text: str) -> tuple[str, bool]:
    """Встроить оговорку в ответ, если пора. Вернуть (текст, добавили ли)."""
    if not should_nudge(rec):
        return text, False
    body = (text or "").rstrip()
    if SHORT_DISCLAIMER in body:
        mark_nudged(rec)
        return text, True
    combined = f"{body}\n\n{SHORT_DISCLAIMER}" if body else SHORT_DISCLAIMER
    mark_nudged(rec)
    return combined, True


def direct_answer_text() -> str:
    return SHORT_DISCLAIMER


def copy_nudge_state(src: MaxIntakeRecord | None, dst: MaxIntakeRecord) -> None:
    """Перезапуск процесса не сбрасывает счётчик."""
    if src is None:
        return
    dst.logical_bot_msg_count = int(src.logical_bot_msg_count or 0)
    dst.submission_nudge_tier = int(src.submission_nudge_tier or 0)
    dst.submission_nudge_at_count = int(src.submission_nudge_at_count or 0)


def intervals_doc() -> dict[str, Any]:
    return {
        "first_after": NUDGE_INTERVALS[0],
        "second_after_more": NUDGE_INTERVALS[1],
        "third_after_more": NUDGE_INTERVALS[2],
        "thereafter_every": NUDGE_INTERVAL_AFTER,
        "note": "Считаются логические сообщения бота; техразбиение одного ответа — один счёт.",
    }
