"""Допуск к предложению платной диагностики 3 000 ₽ (ТЗ-35 / 35a).

Последовательность: краткий разбор → ясный итог клиенту → согласие на
подробный разбор → оффер 3 000 ₽. Kill-switch: MAX_DIAG_OFFER_EF_OPEN.
Пакеты 5 000 / 8 000 и полный этап F этим флагом не открываются.
Старая кнопка diag:yes не обходит условия ниже.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sfrfr.core.config import get_settings

OFFER_TEXT = (
    "Подробная диагностика — 3 000 ₽. "
    "Разберём документы и подготовим понятный план. "
    "Решение о пенсии принимает только СФР."
)
OFFER_BUTTON = "Подробная диагностика — 3 000 ₽"

DENY_NO_ANALYSIS = "no_analysis"
DENY_ANALYSIS_ERROR = "analysis_error"
DENY_STALE_ANALYSIS = "stale_analysis"
DENY_NO_DISCREPANCY = "no_discrepancy"
DENY_NO_CLIENT_CONSENT = "no_detail_consent"
DENY_EF_CLOSED = "ef_closed"
DENY_PRODUCT_GATE = "product_gate"


@dataclass(frozen=True)
class DiagOfferDecision:
    allowed: bool
    reason: str
    offer_text: str | None = None


def ef_stages_open(*, settings: Any | None = None) -> bool:
    cfg = settings or get_settings()
    return bool(getattr(cfg, "max_diag_offer_ef_open", False))


def evaluate_diag_offer(
    *,
    has_completed_brief_analysis: bool,
    analysis_ok: bool,
    analysis_current: bool,
    has_justified_discrepancy: bool,
    client_got_clear_summary: bool,
    client_wants_detailed_review: bool,
    product_gate_allows: bool | None = None,
    settings: Any | None = None,
) -> DiagOfferDecision:
    """Серверная проверка допуска. Скрытие кнопки на клиенте недостаточно."""
    if not ef_stages_open(settings=settings):
        return DiagOfferDecision(False, DENY_EF_CLOSED)
    if product_gate_allows is None:
        gate_ok = ef_stages_open(settings=settings)
    else:
        gate_ok = product_gate_allows
    if not gate_ok:
        return DiagOfferDecision(False, DENY_PRODUCT_GATE)
    if not has_completed_brief_analysis:
        return DiagOfferDecision(False, DENY_NO_ANALYSIS)
    if not analysis_ok:
        return DiagOfferDecision(False, DENY_ANALYSIS_ERROR)
    if not analysis_current:
        return DiagOfferDecision(False, DENY_STALE_ANALYSIS)
    if not has_justified_discrepancy:
        return DiagOfferDecision(False, DENY_NO_DISCREPANCY)
    if not client_got_clear_summary or not client_wants_detailed_review:
        return DiagOfferDecision(False, DENY_NO_CLIENT_CONSENT)
    return DiagOfferDecision(True, "ok", OFFER_TEXT)


def assert_offer_allowed(decision: DiagOfferDecision) -> None:
    if not decision.allowed:
        raise PermissionError(decision.reason)
