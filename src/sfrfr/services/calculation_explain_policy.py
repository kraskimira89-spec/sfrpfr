"""Проверяемость числовых оценок: статус источника, не «убедить поверить».

Не калькулятор пенсии и не генератор прибавки (см. no-calculator-no-recalculation).
Числа клиенту — только из проверяемого механизма / документа; иначе — отказ подтвердить.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Final


class CalculationSubject(StrEnum):
    PERIOD_DURATION = "period_duration"
    PRELIMINARY_ESTIMATE = "preliminary_estimate"
    OFFICIAL_AMOUNT = "official_amount"
    OTHER = "other"


class CalculationStatus(StrEnum):
    """Статус числа для клиента."""

    PRELIMINARY = "preliminary"
    EXPERT_REVIEWED = "expert_reviewed"
    OFFICIAL_DOCUMENT = "official_document"
    UNVERIFIED = "unverified"  # назвали без основания — нельзя подтверждать


class DistrustVariant(StrEnum):
    ASK_SOURCE = "ask_source"  # А: откуда сумма
    DIFFERS_FROM_SFR = "differs_from_sfr"  # Б
    CLIENT_OWN_SUM = "client_own_sum"  # В
    PROMISE_CHANGED = "promise_changed"  # Г
    WANT_HUMAN = "want_human"  # Д


_ASK_SOURCE_RE: Final = re.compile(
    r"откуда\s+(эта\s+)?(цифр|сумм)|не\s+верю.{0,20}(сумм|цифр)|"
    r"должны\s+добавить|откуда\s+взял",
    re.I | re.DOTALL,
)
_DIFFERS_SFR_RE: Final = re.compile(
    r"(у\s+вас|у\s+вас\s+получается).{0,40}(сфр|решени)|"
    r"в\s+решении\s+сфр.{0,30}друг|кто\s+ошиб",
    re.I | re.DOTALL,
)
_OWN_SUM_RE: Final = re.compile(
    r"я\s+(сам|сама)\s+(по)?считал|у\s+меня\s+должно\s+быть|"
    r"сложил\s+все\s+годы",
    re.I,
)
_PROMISE_CHANGED_RE: Final = re.compile(
    r"(вчера|раньше).{0,40}(тысяч|руб|гарантир)|"
    r"сегодня.{0,30}не\s+гарантир|вы\s+меня\s+обманул",
    re.I | re.DOTALL,
)
_WANT_HUMAN_RE: Final = re.compile(
    r"(формул|расч[её]т).{0,30}не\s+вер|"
    r"пусть\s+проверит\s+специалист|нужен\s+человек|"
    r"специалист.{0,20}проверит",
    re.I | re.DOTALL,
)

BANNED_CALC_REPLY_MARKERS: Final[tuple[str, ...]] = (
    "так посчитала система",
    "практически наверняка",
    "гарантируем прибавку",
    "восстановим формулу",
    "сервис точнее сфр",
    "сфр всегда прав",
)


def classify_calculation_distrust(text: str) -> DistrustVariant | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if _WANT_HUMAN_RE.search(raw):
        return DistrustVariant.WANT_HUMAN
    if _PROMISE_CHANGED_RE.search(raw):
        return DistrustVariant.PROMISE_CHANGED
    if _DIFFERS_SFR_RE.search(raw):
        return DistrustVariant.DIFFERS_FROM_SFR
    if _OWN_SUM_RE.search(raw):
        return DistrustVariant.CLIENT_OWN_SUM
    if _ASK_SOURCE_RE.search(raw):
        return DistrustVariant.ASK_SOURCE
    return None


def may_confirm_amount_as_fact(status: CalculationStatus) -> bool:
    """Предварительная / необоснованная оценка ≠ установленный факт."""
    return status in {
        CalculationStatus.EXPERT_REVIEWED,
        CalculationStatus.OFFICIAL_DOCUMENT,
    }


def must_withdraw_unverifiable_amount(
    *,
    named_amount: bool,
    has_reproducible_sources: bool,
    status: CalculationStatus,
) -> bool:
    """Если сумму назвали, а источника нет — нельзя защищать её как факт."""
    if not named_amount:
        return False
    if status == CalculationStatus.UNVERIFIED:
        return True
    if status == CalculationStatus.PRELIMINARY and not has_reproducible_sources:
        return True
    return not has_reproducible_sources and status != CalculationStatus.OFFICIAL_DOCUMENT


def explanation_bundle(
    *,
    subject: CalculationSubject,
    status: CalculationStatus,
    sources: list[str],
    method_plain: str,
    assumptions: list[str],
    limitations: list[str],
    result_label: str,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Структура §23 — для UI/шаблона, не свободная генерация числа."""
    return {
        "subject": subject.value,
        "status": status.value,
        "sources": list(sources),
        "as_of": as_of,
        "method": method_plain,
        "assumptions": list(assumptions),
        "limitations": list(limitations),
        "result": result_label,
        "reproducible": bool(sources) and bool(method_plain.strip()),
        "may_state_as_fact": may_confirm_amount_as_fact(status),
    }


def reply_has_banned_calc_rhetoric(reply: str) -> bool:
    low = (reply or "").casefold()
    return any(m in low for m in BANNED_CALC_REPLY_MARKERS)


def paid_dispute_is_claim_not_price_objection(distrust: DistrustVariant) -> bool:
    """Спорная сумма повлияла на покупку → претензия (§20.17 Г)."""
    return distrust == DistrustVariant.PROMISE_CHANGED
