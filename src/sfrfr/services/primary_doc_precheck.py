"""Первичная проверка документов: сопоставление → outcome → резюме → рекомендация.

Не обещает пенсию/прибавку. Не правит канонические даты.
Платный анализ — только при конкретной задаче из находок.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

RULES_VERSION = "primary-doc-precheck-v1"


class PrecheckOutcome(StrEnum):
    DISCREPANCIES_FOUND = "discrepancies_found"
    NEEDS_CLARIFICATION = "needs_clarification"
    INSUFFICIENT_DOCUMENTS = "insufficient_documents"
    NO_DISCREPANCIES_FOUND = "no_discrepancies_found"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    FAILED = "failed"


@dataclass
class PrecheckFinding:
    what: str
    period_ref: str | None
    source_a: str
    source_b: str
    discrepancy_type: str
    extraction_confidence: str
    confirmed: bool
    needs_review: bool
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PrecheckRecommendation:
    offer_paid_analysis: bool
    reason: str
    package_code: str | None = None
    package_label: str | None = None
    amount_rub: int | None = None
    primary_cta: str = "view_summary"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PrimaryPrecheckResult:
    outcome: PrecheckOutcome
    findings: list[PrecheckFinding] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    areas_checked: list[str] = field(default_factory=list)
    client_summary: str = ""
    recommendation: PrecheckRecommendation | None = None
    rules_version: str = RULES_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "findings": [f.as_dict() for f in self.findings],
            "limitations": list(self.limitations),
            "areas_checked": list(self.areas_checked),
            "client_summary": self.client_summary,
            "recommendation": (
                self.recommendation.as_dict() if self.recommendation else None
            ),
            "rules_version": self.rules_version,
            "built_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        }


def _norm_date(value: Any) -> str | None:
    raw = str(value or "").strip()
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]
    return raw or None


def _period_key(period: dict[str, Any]) -> str:
    emp = str(period.get("employer") or "").strip().casefold()
    df = _norm_date(period.get("date_from")) or ""
    dt = _norm_date(period.get("date_to")) or ""
    return f"{emp}|{df}|{dt}"


def compare_period_sources(
    *,
    ils_periods: list[dict[str, Any]] | None,
    labor_periods: list[dict[str, Any]] | None,
) -> list[PrecheckFinding]:
    """Сопоставить ИЛС и трудовую: даты, пропуски, пересечения-кандидаты."""
    from sfrfr.core.audit_ils import compare_ils_vs_labor_book

    ils = [dict(p) for p in (ils_periods or []) if isinstance(p, dict)]
    labor = [dict(p) for p in (labor_periods or []) if isinstance(p, dict)]
    findings: list[PrecheckFinding] = []

    for raw in compare_ils_vs_labor_book(ils, labor):
        if not isinstance(raw, dict):
            continue
        findings.append(
            PrecheckFinding(
                what=str(raw.get("detail") or raw.get("type") or "расхождение"),
                period_ref=str(raw.get("period_ref") or "") or None,
                source_a=str(raw.get("source_a") or "ils"),
                source_b=str(raw.get("source_b") or "labor_book"),
                discrepancy_type=str(raw.get("type") or "mismatch"),
                extraction_confidence=str(raw.get("confidence") or "medium"),
                confirmed=False,
                needs_review=True,
                next_action=str(raw.get("next_action") or "detailed_review"),
            )
        )

    # Попарное сравнение дат при совпадающем работодателе.
    labor_by_emp: dict[str, list[dict[str, Any]]] = {}
    for p in labor:
        emp = str(p.get("employer") or "").strip().casefold() or "_"
        labor_by_emp.setdefault(emp, []).append(p)
    for ip in ils:
        emp = str(ip.get("employer") or "").strip().casefold() or "_"
        candidates = labor_by_emp.get(emp) or []
        if not candidates:
            continue
        idf, idt = _norm_date(ip.get("date_from")), _norm_date(ip.get("date_to"))
        for lp in candidates:
            ldf, ldt = _norm_date(lp.get("date_from")), _norm_date(lp.get("date_to"))
            if idf and ldf and idf != ldf:
                findings.append(
                    PrecheckFinding(
                        what=f"Разные даты начала у «{ip.get('employer') or 'работодатель'}»",
                        period_ref=_period_key(ip),
                        source_a=f"ils:{idf}",
                        source_b=f"labor:{ldf}",
                        discrepancy_type="date_from_mismatch",
                        extraction_confidence="medium",
                        confirmed=False,
                        needs_review=True,
                        next_action="detailed_review",
                    )
                )
            if idt and ldt and idt != ldt:
                findings.append(
                    PrecheckFinding(
                        what=f"Разные даты окончания у «{ip.get('employer') or 'работодатель'}»",
                        period_ref=_period_key(ip),
                        source_a=f"ils:{idt}",
                        source_b=f"labor:{ldt}",
                        discrepancy_type="date_to_mismatch",
                        extraction_confidence="medium",
                        confirmed=False,
                        needs_review=True,
                        next_action="detailed_review",
                    )
                )
    return findings


def choose_outcome(
    *,
    kit_missing: list[str],
    needs_ocr: int,
    originals_missing: int,
    findings: list[PrecheckFinding],
    ils_count: int,
    labor_count: int,
    low_confidence_count: int = 0,
) -> tuple[PrecheckOutcome, list[str]]:
    limitations: list[str] = []
    if originals_missing > 0 or needs_ocr > 0 or kit_missing:
        limitations.append("Неполный или нечитаемый комплект ограничивает сопоставление.")
        return PrecheckOutcome.INSUFFICIENT_DOCUMENTS, limitations
    if ils_count == 0 and labor_count == 0:
        limitations.append("Нет извлечённых периодов для сопоставления.")
        return PrecheckOutcome.INSUFFICIENT_DOCUMENTS, limitations
    if ils_count == 0 or labor_count == 0:
        limitations.append("Есть только один тип источника периодов.")
        if findings:
            return PrecheckOutcome.NEEDS_CLARIFICATION, limitations
        return PrecheckOutcome.INSUFFICIENT_DOCUMENTS, limitations
    if low_confidence_count > 0 and not findings:
        limitations.append("Низкая уверенность извлечения — нужен ручной просмотр.")
        return PrecheckOutcome.MANUAL_REVIEW_REQUIRED, limitations
    hard = [
        f
        for f in findings
        if f.discrepancy_type
        in {
            "date_from_mismatch",
            "date_to_mismatch",
            "missing_in_ils",
            "missing_in_labor",
            "overlap_suspect",
        }
    ]
    if hard:
        limitations.append(
            "Расхождения зафиксированы как вопросы к проверке, "
            "не как доказанная ошибка пенсии."
        )
        return PrecheckOutcome.DISCREPANCIES_FOUND, limitations
    if findings:
        return PrecheckOutcome.NEEDS_CLARIFICATION, limitations
    limitations.append(
        "Это результат первичной проверки представленных сведений, "
        "а не подтверждение правильности всех пенсионных расчётов."
    )
    return PrecheckOutcome.NO_DISCREPANCIES_FOUND, limitations


def build_client_summary(
    outcome: PrecheckOutcome,
    findings: list[PrecheckFinding],
) -> str:
    if outcome == PrecheckOutcome.DISCREPANCIES_FOUND:
        sample = findings[0].what if findings else "периоду"
        return (
            "Мы сопоставили доступные сведения ИЛС и документы о работе. "
            f"Нашли расхождение: {sample}. "
            "Пока это не подтверждает ошибку в размере пенсии. "
            "Рекомендуем подробный анализ, чтобы проверить основания учёта "
            "периода и определить дальнейшие действия."
        )
    if outcome == PrecheckOutcome.INSUFFICIENT_DOCUMENTS:
        return (
            "По полученным файлам пока нельзя надёжно сравнить сведения. "
            "Нужны недостающие или более читаемые страницы с записями. "
            "После загрузки продолжим проверку."
        )
    if outcome == PrecheckOutcome.NEEDS_CLARIFICATION:
        return (
            "По документам есть неоднозначность, которую нужно уточнить "
            "до выводов о учёте периодов. Мы подскажем, какой документ "
            "или пояснение поможет."
        )
    if outcome == PrecheckOutcome.MANUAL_REVIEW_REQUIRED:
        return (
            "Автоматическая первичная проверка не даёт достаточно надёжного "
            "вывода. Сотрудник посмотрит материалы и сообщит следующий шаг."
        )
    if outcome == PrecheckOutcome.FAILED:
        return (
            "Технический сбой первичной проверки. Результат не сформирован — "
            "можно повторить позже или обратиться к сотруднику."
        )
    return (
        "В сопоставленных документах явных расхождений не обнаружили. "
        "Это результат первичной проверки представленных сведений, "
        "а не подтверждение правильности всех пенсионных расчётов."
    )


def build_recommendation(
    outcome: PrecheckOutcome,
    *,
    already_ordered_or_paid: bool,
    catalog_amount_rub: int | None,
    catalog_label: str | None,
    package_code: str | None,
) -> PrecheckRecommendation:
    """Платный анализ только при конкретной задаче; не при incomplete/no_discrepancy/fail."""
    if already_ordered_or_paid:
        return PrecheckRecommendation(
            offer_paid_analysis=False,
            reason="Услуга подробного анализа уже заказана или оплачена.",
            primary_cta="ask_staff",
        )
    if outcome == PrecheckOutcome.DISCREPANCIES_FOUND:
        if catalog_amount_rub is None:
            return PrecheckRecommendation(
                offer_paid_analysis=False,
                reason="Каталог услуг недоступен — свяжитесь с сотрудником.",
                primary_cta="ask_staff",
            )
        return PrecheckRecommendation(
            offer_paid_analysis=True,
            reason=(
                "Нужна углублённая проверка оснований учёта периода "
                "и подготовка понятного плана действий."
            ),
            package_code=package_code,
            package_label=catalog_label or "Подробный анализ",
            amount_rub=catalog_amount_rub,
            primary_cta="order_detailed_analysis",
        )
    if outcome == PrecheckOutcome.NEEDS_CLARIFICATION:
        return PrecheckRecommendation(
            offer_paid_analysis=False,
            reason="Сначала уточнение документов или фактов.",
            primary_cta="request_docs",
        )
    if outcome == PrecheckOutcome.INSUFFICIENT_DOCUMENTS:
        return PrecheckRecommendation(
            offer_paid_analysis=False,
            reason="Недостаточно документов для сопоставления.",
            primary_cta="request_docs",
        )
    if outcome == PrecheckOutcome.NO_DISCREPANCIES_FOUND:
        return PrecheckRecommendation(
            offer_paid_analysis=False,
            reason="Нет оснований предлагать платный анализ после первичной проверки.",
            primary_cta="view_summary",
        )
    return PrecheckRecommendation(
        offer_paid_analysis=False,
        reason="Нужен сотрудник или повтор проверки.",
        primary_cta="ask_staff",
    )


def run_primary_precheck(
    *,
    ils_periods: list[dict[str, Any]] | None,
    labor_periods: list[dict[str, Any]] | None,
    kit_missing: list[str] | None = None,
    needs_ocr: int = 0,
    originals_missing: int = 0,
    already_ordered_or_paid: bool = False,
    catalog_amount_rub: int | None = None,
    catalog_label: str | None = None,
    package_code: str | None = None,
) -> PrimaryPrecheckResult:
    ils = [p for p in (ils_periods or []) if isinstance(p, dict)]
    labor = [p for p in (labor_periods or []) if isinstance(p, dict)]
    findings = compare_period_sources(ils_periods=ils, labor_periods=labor)
    outcome, limitations = choose_outcome(
        kit_missing=list(kit_missing or []),
        needs_ocr=needs_ocr,
        originals_missing=originals_missing,
        findings=findings,
        ils_count=len(ils),
        labor_count=len(labor),
    )
    rec = build_recommendation(
        outcome,
        already_ordered_or_paid=already_ordered_or_paid,
        catalog_amount_rub=catalog_amount_rub,
        catalog_label=catalog_label,
        package_code=package_code,
    )
    return PrimaryPrecheckResult(
        outcome=outcome,
        findings=findings,
        limitations=limitations,
        areas_checked=["ils_vs_labor_periods", "kit_completeness", "readability"],
        client_summary=build_client_summary(outcome, findings),
        recommendation=rec,
    )
