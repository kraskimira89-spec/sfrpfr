"""Публичные формулировки сервиса (единый источник)."""

from __future__ import annotations

# Эталон: scripts/assets/copy/submission-position.md
POSITION_FULL = (
    "Мы готовим документы, черновики и понятный план. "
    "А подаёте обращение через СФР, МФЦ или Госуслуги вы сами. "
    "Решение о пенсии и перерасчёте принимает только СФР."
)

POSITION_SHORT = (
    "Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. "
    "Решение принимает СФР."
)

SUBMISSION_INSTRUCTION = POSITION_SHORT

WARNING = f"{POSITION_SHORT} Результат не гарантирован."
