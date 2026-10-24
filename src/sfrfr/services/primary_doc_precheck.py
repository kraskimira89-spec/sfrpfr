"""Слой 1–2: доказательные находки и выбор next_action.

Коммерция не влияет на comparison_status. Рекомендация услуги — отдельно
(`build_recommendation_card`), после фиксации находок.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

RULES_VERSION = "primary-doc-precheck-v2"


class FindingCode(StrEnum):
    MATCHED = "MATCHED"
    DATE_DIFFERENCE = "DATE_DIFFERENCE"
    PARTIAL_COVERAGE = "PARTIAL_COVERAGE"
    NOT_LOCATED_IN_ILS = "NOT_LOCATED_IN_ILS"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    UNREADABLE_OR_INCOMPLETE = "UNREADABLE_OR_INCOMPLETE"
    SPECIAL_CONDITIONS_REVIEW = "SPECIAL_CONDITIONS_REVIEW"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    EMPLOYER_CANDIDATE = "EMPLOYER_CANDIDATE"


class ExecutionStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class DataStatus(StrEnum):
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"
    IDENTITY_CONFLICT = "identity_conflict"


class ComparisonStatus(StrEnum):
    DISCREPANCIES_FOUND = "discrepancies_found"
    NO_DISCREPANCIES_FOUND = "no_discrepancies_found"
    INCONCLUSIVE = "inconclusive"


class NextAction(StrEnum):
    UPLOAD_DOCUMENTS = "upload_documents"
    ANSWER_QUESTION = "answer_question"
    STAFF_REVIEW = "staff_review"
    DETAILED_ANALYSIS = "detailed_analysis"
    NO_IMMEDIATE_ACTION = "no_immediate_action"
    RECOVER_PROCESSING = "recover_processing"


# Совместимость со старым API / UI.
class PrecheckOutcome(StrEnum):
    DISCREPANCIES_FOUND = "discrepancies_found"
    NEEDS_CLARIFICATION = "needs_clarification"
    INSUFFICIENT_DOCUMENTS = "insufficient_documents"
    NO_DISCREPANCIES_FOUND = "no_discrepancies_found"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    FAILED = "failed"


_LEGAL_FORMS = re.compile(
    r"\b(ооо|оао|зао|пао|ао|ип|фгуп|муп|гбу|фгау)\b",
    re.IGNORECASE,
)


def normalize_employer(value: Any) -> str:
    raw = str(value or "").casefold()
    raw = _LEGAL_FORMS.sub(" ", raw)
    raw = re.sub(r"[\"'«».,\-_/\\]+", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()


def date_precision(value: Any) -> str:
    raw = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return "day"
    if re.fullmatch(r"\d{4}-\d{2}", raw) or re.fullmatch(r"\d{2}\.\d{4}", raw):
        return "month"
    if re.fullmatch(r"\d{4}", raw):
        return "year"
    if not raw:
        return "none"
    return "uncertain"


def _norm_day(value: Any) -> str | None:
    raw = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    return None


@dataclass
class PrecheckFinding:
    code: FindingCode
    what: str
    period_ref: str | None = None
    source_a: str = "ils"
    source_b: str = "labor_book"
    discrepancy_type: str = ""
    extraction_confidence: str = "medium"
    confirmed: bool = False
    needs_review: bool = True
    next_action: str = "detailed_review"
    finding_id: str | None = None

    def __post_init__(self) -> None:
        if not self.discrepancy_type:
            self.discrepancy_type = self.code.value
        if not self.finding_id:
            self.finding_id = f"{self.code.value}:{self.period_ref or self.what[:40]}"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RecommendationCard:
    recommendation_type: str
    reason_codes: list[str]
    finding_ids: list[str]
    questions_to_resolve: list[str]
    service_code: str | None
    service_scope: str | None
    catalog_price_reference: int | None
    limitations: list[str]
    alternative_next_step: str
    offer_status: str  # allowed | blocked | not_applicable | declined
    package_label: str | None = None

    @property
    def offer_paid_analysis(self) -> bool:
        return self.offer_status == "allowed"

    @property
    def reason(self) -> str:
        return "; ".join(self.questions_to_resolve) or self.recommendation_type

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["offer_paid_analysis"] = self.offer_paid_analysis
        data["amount_rub"] = self.catalog_price_reference
        data["reason"] = self.reason
        data["primary_cta"] = (
            "order_detailed_analysis"
            if self.offer_paid_analysis
            else self.alternative_next_step
        )
        return data


# Alias для старых импортов/тестов.
PrecheckRecommendation = RecommendationCard


@dataclass
class PrimaryPrecheckResult:
    execution_status: ExecutionStatus
    data_status: DataStatus
    comparison_status: ComparisonStatus
    next_action: NextAction
    findings: list[PrecheckFinding] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    areas_checked: list[str] = field(default_factory=list)
    client_summary: str = ""
    recommendation: RecommendationCard | None = None
    rules_version: str = RULES_VERSION
    # legacy mirror
    outcome: PrecheckOutcome = PrecheckOutcome.NO_DISCREPANCIES_FOUND

    def as_dict(self) -> dict[str, Any]:
        return {
            "execution_status": self.execution_status.value,
            "data_status": self.data_status.value,
            "comparison_status": self.comparison_status.value,
            "next_action": self.next_action.value,
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


def compare_period_sources(
    *,
    ils_periods: list[dict[str, Any]] | None,
    labor_periods: list[dict[str, Any]] | None,
    identity_conflict: bool = False,
) -> list[PrecheckFinding]:
    """Доказательные находки. Без коммерческих флагов."""
    if identity_conflict:
        return [
            PrecheckFinding(
                code=FindingCode.IDENTITY_CONFLICT,
                what="Документы предположительно принадлежат разным людям",
                source_a="identity",
                source_b="identity",
                extraction_confidence="high",
                next_action="staff_review",
            )
        ]

    ils = [dict(p) for p in (ils_periods or []) if isinstance(p, dict)]
    labor = [dict(p) for p in (labor_periods or []) if isinstance(p, dict)]
    findings: list[PrecheckFinding] = []

    if not ils and not labor:
        return [
            PrecheckFinding(
                code=FindingCode.UNREADABLE_OR_INCOMPLETE,
                what="Нет извлечённых периодов для сопоставления",
                extraction_confidence="high",
                next_action="upload_documents",
            )
        ]
    if not ils and labor:
        findings.append(
            PrecheckFinding(
                code=FindingCode.NOT_COMPARABLE,
                what="Есть трудовая, нет извлечённых периодов ИЛС",
                source_a="labor_book",
                source_b="ils",
                next_action="upload_documents",
            )
        )
        return findings
    if ils and not labor:
        findings.append(
            PrecheckFinding(
                code=FindingCode.NOT_COMPARABLE,
                what="Есть ИЛС, нет трудовой для сверки",
                source_a="ils",
                source_b="labor_book",
                next_action="upload_documents",
            )
        )
        return findings

    # Группы ИЛС по работодателю — один период трудовой может покрывать несколько строк.
    ils_by_emp: dict[str, list[dict[str, Any]]] = {}
    for p in ils:
        ils_by_emp.setdefault(normalize_employer(p.get("employer")), []).append(p)
    labor_by_emp: dict[str, list[dict[str, Any]]] = {}
    for p in labor:
        labor_by_emp.setdefault(normalize_employer(p.get("employer")), []).append(p)

    matched_emps: set[str] = set()
    for emp, labor_rows in labor_by_emp.items():
        if not emp:
            continue
        ils_rows = ils_by_emp.get(emp)
        if not ils_rows:
            # Нечёткое совпадение названия → кандидат, не авто-ошибка.
            fuzzy = _fuzzy_employer_hit(emp, list(ils_by_emp.keys()))
            if fuzzy:
                findings.append(
                    PrecheckFinding(
                        code=FindingCode.EMPLOYER_CANDIDATE,
                        what=(
                            "Похожие названия работодателя; нужно подтверждение "
                            f"соответствия («{emp}» ≈ «{fuzzy}»)"
                        ),
                        period_ref=emp,
                        extraction_confidence="low",
                        next_action="answer_question",
                    )
                )
                continue
            findings.append(
                PrecheckFinding(
                    code=FindingCode.NOT_LOCATED_IN_ILS,
                    what=(
                        "Документальная запись есть; соответствие в представленной "
                        f"ИЛС не найдено («{emp or 'работодатель'}»)"
                    ),
                    period_ref=emp,
                    source_a="labor_book",
                    source_b="ils",
                    extraction_confidence="medium",
                    next_action="detailed_review",
                )
            )
            continue

        matched_emps.add(emp)
        # Несколько строк ИЛС под одним работодателем ≠ пропуск.
        if len(ils_rows) > 1:
            findings.append(
                PrecheckFinding(
                    code=FindingCode.MATCHED,
                    what=(
                        f"Период «{emp}» представлен несколькими строками ИЛС "
                        "— ложного пропуска нет"
                    ),
                    period_ref=emp,
                    extraction_confidence="medium",
                    confirmed=False,
                    needs_review=False,
                    next_action="no_immediate_action",
                )
            )

        for lr in labor_rows:
            ldf, ldt = _norm_day(lr.get("date_from")), _norm_day(lr.get("date_to"))
            if date_precision(lr.get("date_from")) in {"year", "uncertain"} or (
                lr.get("date_to")
                and date_precision(lr.get("date_to")) in {"year", "uncertain"}
            ):
                findings.append(
                    PrecheckFinding(
                        code=FindingCode.UNREADABLE_OR_INCOMPLETE,
                        what="Дата распознана неуверенно — нужно уточнение, не автовывод",
                        period_ref=emp,
                        extraction_confidence="low",
                        next_action="answer_question",
                    )
                )
                continue
            for ir in ils_rows:
                idf, idt = _norm_day(ir.get("date_from")), _norm_day(ir.get("date_to"))
                if idf and ldf and idf != ldf:
                    findings.append(
                        PrecheckFinding(
                            code=FindingCode.DATE_DIFFERENCE,
                            what=f"Различаются даты начала («{emp}»)",
                            period_ref=emp,
                            source_a=f"ils:{idf}",
                            source_b=f"labor:{ldf}",
                            next_action="detailed_review",
                        )
                    )
                if idt and ldt and idt != ldt:
                    findings.append(
                        PrecheckFinding(
                            code=FindingCode.DATE_DIFFERENCE,
                            what=f"Различаются даты окончания («{emp}»)",
                            period_ref=emp,
                            source_a=f"ils:{idt}",
                            source_b=f"labor:{ldt}",
                            next_action="detailed_review",
                        )
                    )

    for emp in ils_by_emp:
        if emp and emp not in matched_emps and emp not in labor_by_emp:
            if _fuzzy_employer_hit(emp, list(labor_by_emp.keys())):
                continue
            findings.append(
                PrecheckFinding(
                    code=FindingCode.PARTIAL_COVERAGE,
                    what=f"Запись ИЛС без пары в трудовой («{emp}») — проверить покрытие",
                    period_ref=emp,
                    source_a="ils",
                    source_b="labor_book",
                    extraction_confidence="low",
                    next_action="answer_question",
                )
            )

    if not findings:
        findings.append(
            PrecheckFinding(
                code=FindingCode.MATCHED,
                what="В сопоставимых фрагментах расхождений не обнаружено",
                needs_review=False,
                next_action="no_immediate_action",
            )
        )
    return findings


def _fuzzy_employer_hit(needle: str, haystack: list[str]) -> str | None:
    if not needle:
        return None
    for cand in haystack:
        if not cand:
            continue
        if needle in cand or cand in needle:
            return cand
        # общие токены длиной ≥4
        nt = {t for t in needle.split() if len(t) >= 4}
        ct = {t for t in cand.split() if len(t) >= 4}
        if nt and ct and nt & ct:
            return cand
    return None


def derive_statuses(
    findings: list[PrecheckFinding],
    *,
    kit_missing: list[str],
    needs_ocr: int,
    originals_missing: int,
    failed: bool = False,
) -> tuple[ExecutionStatus, DataStatus, ComparisonStatus, NextAction, PrecheckOutcome]:
    if failed:
        return (
            ExecutionStatus.FAILED,
            DataStatus.INSUFFICIENT,
            ComparisonStatus.INCONCLUSIVE,
            NextAction.RECOVER_PROCESSING,
            PrecheckOutcome.FAILED,
        )
    if any(f.code == FindingCode.IDENTITY_CONFLICT for f in findings):
        return (
            ExecutionStatus.COMPLETED,
            DataStatus.IDENTITY_CONFLICT,
            ComparisonStatus.INCONCLUSIVE,
            NextAction.STAFF_REVIEW,
            PrecheckOutcome.MANUAL_REVIEW_REQUIRED,
        )
    incomplete = originals_missing > 0 or needs_ocr > 0 or bool(kit_missing)
    hard = {
        FindingCode.DATE_DIFFERENCE,
        FindingCode.NOT_LOCATED_IN_ILS,
        FindingCode.SOURCE_CONFLICT,
    }
    soft = {
        FindingCode.UNREADABLE_OR_INCOMPLETE,
        FindingCode.EMPLOYER_CANDIDATE,
        FindingCode.PARTIAL_COVERAGE,
        FindingCode.SPECIAL_CONDITIONS_REVIEW,
        FindingCode.NOT_COMPARABLE,
    }
    has_hard = any(f.code in hard for f in findings)
    has_soft = any(f.code in soft for f in findings)
    only_matched = findings and all(f.code == FindingCode.MATCHED for f in findings)

    if incomplete and not has_hard:
        return (
            ExecutionStatus.COMPLETED,
            DataStatus.INSUFFICIENT if (kit_missing or originals_missing) else DataStatus.PARTIAL,
            ComparisonStatus.INCONCLUSIVE,
            NextAction.UPLOAD_DOCUMENTS,
            PrecheckOutcome.INSUFFICIENT_DOCUMENTS,
        )
    if has_hard and incomplete:
        # Находка + неполнота одновременно.
        return (
            ExecutionStatus.COMPLETED,
            DataStatus.PARTIAL,
            ComparisonStatus.DISCREPANCIES_FOUND,
            NextAction.DETAILED_ANALYSIS,
            PrecheckOutcome.DISCREPANCIES_FOUND,
        )
    if has_hard:
        return (
            ExecutionStatus.COMPLETED,
            DataStatus.SUFFICIENT,
            ComparisonStatus.DISCREPANCIES_FOUND,
            NextAction.DETAILED_ANALYSIS,
            PrecheckOutcome.DISCREPANCIES_FOUND,
        )
    if has_soft:
        needs_answer = any(
            f.code
            in {
                FindingCode.EMPLOYER_CANDIDATE,
                FindingCode.UNREADABLE_OR_INCOMPLETE,
                FindingCode.PARTIAL_COVERAGE,
            }
            for f in findings
        )
        return (
            ExecutionStatus.COMPLETED,
            DataStatus.PARTIAL,
            ComparisonStatus.INCONCLUSIVE,
            NextAction.ANSWER_QUESTION if needs_answer else NextAction.STAFF_REVIEW,
            PrecheckOutcome.NEEDS_CLARIFICATION
            if needs_answer
            else PrecheckOutcome.MANUAL_REVIEW_REQUIRED,
        )
    if only_matched:
        return (
            ExecutionStatus.COMPLETED,
            DataStatus.SUFFICIENT,
            ComparisonStatus.NO_DISCREPANCIES_FOUND,
            NextAction.NO_IMMEDIATE_ACTION,
            PrecheckOutcome.NO_DISCREPANCIES_FOUND,
        )
    return (
        ExecutionStatus.COMPLETED,
        DataStatus.PARTIAL,
        ComparisonStatus.INCONCLUSIVE,
        NextAction.STAFF_REVIEW,
        PrecheckOutcome.MANUAL_REVIEW_REQUIRED,
    )


def build_client_summary(
    *,
    comparison_status: ComparisonStatus,
    data_status: DataStatus,
    findings: list[PrecheckFinding],
    next_action: NextAction,
) -> str:
    hard = [f for f in findings if f.code == FindingCode.DATE_DIFFERENCE]
    if comparison_status == ComparisonStatus.DISCREPANCIES_FOUND:
        sample = hard[0].what if hard else (
            findings[0].what if findings else "периоду"
        )
        extra = ""
        if data_status == DataStatus.PARTIAL:
            extra = " Часть документов ещё не проверена из‑за неполноты комплекта."
        return (
            "В документах нашли различие по записям о работе "
            f"({sample}). Это пока не доказывает ошибку в размере пенсии. "
            "В резюме показали, какие записи отличаются и что нужно проверить дальше."
            + extra
        )
    if next_action == NextAction.UPLOAD_DOCUMENTS:
        return (
            "По полученным файлам пока нельзя надёжно сравнить сведения. "
            "Нужны конкретные недостающие или более читаемые страницы. "
            "После загрузки продолжим проверку."
        )
    if next_action == NextAction.STAFF_REVIEW:
        return (
            "Автоматический вывод недостаточен (качество, принадлежность или "
            "структура сведений). Сотрудник посмотрит материалы."
        )
    if next_action == NextAction.RECOVER_PROCESSING:
        return "Проверка не завершена из‑за технического сбоя. Выводов пока нет."
    if comparison_status == ComparisonStatus.NO_DISCREPANCIES_FOUND:
        return (
            "В сопоставленных фрагментах явных расхождений не обнаружили. "
            "Это результат первичной проверки представленных сведений, "
            "а не подтверждение правильности всех пенсионных расчётов."
        )
    return (
        "Есть неоднозначность в сопоставлении. Нужно уточнение до выводов "
        "о учёте периодов."
    )


def build_recommendation_card(
    *,
    comparison_status: ComparisonStatus,
    next_action: NextAction,
    findings: list[PrecheckFinding],
    already_ordered_or_paid: bool,
    client_declined_offer: bool,
    catalog_amount_rub: int | None,
    catalog_label: str | None,
    package_code: str | None,
) -> RecommendationCard:
    """Слой 2: коммерция только здесь; не меняет findings/comparison_status."""
    # Только содержательные находки с источниками; не OCR-шум.
    hard_findings = [
        f
        for f in findings
        if f.code
        in {
            FindingCode.DATE_DIFFERENCE,
            FindingCode.NOT_LOCATED_IN_ILS,
            FindingCode.SOURCE_CONFLICT,
        }
        and f.extraction_confidence != "low"
        and bool(f.source_a and f.source_b)
    ]
    hard_ids = [f.finding_id or f.code.value for f in hard_findings]
    if already_ordered_or_paid:
        return RecommendationCard(
            recommendation_type="none",
            reason_codes=["already_ordered"],
            finding_ids=hard_ids,
            questions_to_resolve=[],
            service_code=None,
            service_scope=None,
            catalog_price_reference=None,
            limitations=["Услуга уже заказана или оплачена."],
            alternative_next_step="ask_staff",
            offer_status="blocked",
        )
    if client_declined_offer:
        return RecommendationCard(
            recommendation_type="none",
            reason_codes=["client_declined"],
            finding_ids=hard_ids,
            questions_to_resolve=[],
            service_code=None,
            service_scope=None,
            catalog_price_reference=None,
            limitations=["Клиент отказался от предложения."],
            alternative_next_step="view_summary",
            offer_status="declined",
        )
    if next_action == NextAction.RECOVER_PROCESSING:
        return RecommendationCard(
            recommendation_type="none",
            reason_codes=["technical_failure"],
            finding_ids=[],
            questions_to_resolve=[],
            service_code=None,
            service_scope=None,
            catalog_price_reference=None,
            limitations=["Техсбой не основание для продажи."],
            alternative_next_step="recover",
            offer_status="not_applicable",
        )
    if next_action == NextAction.UPLOAD_DOCUMENTS:
        return RecommendationCard(
            recommendation_type="upload_documents",
            reason_codes=["insufficient_data"],
            finding_ids=[],
            questions_to_resolve=["Нужны недостающие/читаемые документы."],
            service_code=None,
            service_scope=None,
            catalog_price_reference=None,
            limitations=[],
            alternative_next_step="request_docs",
            offer_status="not_applicable",
        )
    if (
        comparison_status == ComparisonStatus.DISCREPANCIES_FOUND
        and next_action == NextAction.DETAILED_ANALYSIS
        and hard_ids
    ):
        if catalog_amount_rub is None:
            return RecommendationCard(
                recommendation_type="staff_contact",
                reason_codes=["catalog_unavailable"],
                finding_ids=hard_ids,
                questions_to_resolve=[
                    "Проверить основания учёта периода с расхождением дат/отражения."
                ],
                service_code=None,
                service_scope=None,
                catalog_price_reference=None,
                limitations=["Каталог недоступен — без произвольной цены."],
                alternative_next_step="ask_staff",
                offer_status="blocked",
            )
        return RecommendationCard(
            recommendation_type="detailed_analysis",
            reason_codes=["date_or_location_discrepancy"],
            finding_ids=hard_ids,
            questions_to_resolve=[
                "Как период отражён в пенсионных документах и какие действия обоснованы."
            ],
            service_code=package_code,
            service_scope=(
                "Проверка оснований учёта периода и подготовка понятного плана. "
                "Не обещает увеличение пенсии."
            ),
            catalog_price_reference=catalog_amount_rub,
            limitations=[
                "Рекомендация исследования, не обещание положительного результата."
            ],
            alternative_next_step="view_summary",
            offer_status="allowed",
            package_label=catalog_label or "Подробный анализ",
        )
    if comparison_status == ComparisonStatus.NO_DISCREPANCIES_FOUND:
        return RecommendationCard(
            recommendation_type="none",
            reason_codes=["no_discrepancies"],
            finding_ids=[],
            questions_to_resolve=[],
            service_code=None,
            service_scope=None,
            catalog_price_reference=None,
            limitations=["Нет обязательной продажи после «нет расхождений»."],
            alternative_next_step="view_summary",
            offer_status="not_applicable",
        )
    return RecommendationCard(
        recommendation_type="clarify",
        reason_codes=["inconclusive"],
        finding_ids=[f.finding_id or f.code.value for f in findings[:5]],
        questions_to_resolve=["Уточнить неоднозначность источников."],
        service_code=None,
        service_scope=None,
        catalog_price_reference=None,
        limitations=[],
        alternative_next_step="ask_staff",
        offer_status="not_applicable",
    )


def run_primary_precheck(
    *,
    ils_periods: list[dict[str, Any]] | None,
    labor_periods: list[dict[str, Any]] | None,
    kit_missing: list[str] | None = None,
    needs_ocr: int = 0,
    originals_missing: int = 0,
    identity_conflict: bool = False,
    failed: bool = False,
    already_ordered_or_paid: bool = False,
    client_declined_offer: bool = False,
    catalog_amount_rub: int | None = None,
    catalog_label: str | None = None,
    package_code: str | None = None,
) -> PrimaryPrecheckResult:
    findings = compare_period_sources(
        ils_periods=ils_periods,
        labor_periods=labor_periods,
        identity_conflict=identity_conflict,
    )
    execution, data, comparison, next_action, outcome = derive_statuses(
        findings,
        kit_missing=list(kit_missing or []),
        needs_ocr=needs_ocr,
        originals_missing=originals_missing,
        failed=failed,
    )
    # Рекомендация строится ПОСЛЕ статусов и не меняет comparison_status.
    rec = build_recommendation_card(
        comparison_status=comparison,
        next_action=next_action,
        findings=findings,
        already_ordered_or_paid=already_ordered_or_paid,
        client_declined_offer=client_declined_offer,
        catalog_amount_rub=catalog_amount_rub,
        catalog_label=catalog_label,
        package_code=package_code,
    )
    summary = build_client_summary(
        comparison_status=comparison,
        data_status=data,
        findings=findings,
        next_action=next_action,
    )
    return PrimaryPrecheckResult(
        execution_status=execution,
        data_status=data,
        comparison_status=comparison,
        next_action=next_action,
        findings=findings,
        limitations=list(rec.limitations),
        areas_checked=["ils_vs_labor_periods", "kit_completeness", "readability"],
        client_summary=summary,
        recommendation=rec,
        outcome=outcome,
    )


# Совместимость со старым именем.
def build_recommendation(
    outcome: PrecheckOutcome,
    *,
    already_ordered_or_paid: bool,
    catalog_amount_rub: int | None,
    catalog_label: str | None,
    package_code: str | None,
) -> RecommendationCard:
    comparison = {
        PrecheckOutcome.DISCREPANCIES_FOUND: ComparisonStatus.DISCREPANCIES_FOUND,
        PrecheckOutcome.NO_DISCREPANCIES_FOUND: ComparisonStatus.NO_DISCREPANCIES_FOUND,
    }.get(outcome, ComparisonStatus.INCONCLUSIVE)
    next_action = {
        PrecheckOutcome.DISCREPANCIES_FOUND: NextAction.DETAILED_ANALYSIS,
        PrecheckOutcome.INSUFFICIENT_DOCUMENTS: NextAction.UPLOAD_DOCUMENTS,
        PrecheckOutcome.NO_DISCREPANCIES_FOUND: NextAction.NO_IMMEDIATE_ACTION,
        PrecheckOutcome.FAILED: NextAction.RECOVER_PROCESSING,
    }.get(outcome, NextAction.STAFF_REVIEW)
    dummy = [
        PrecheckFinding(code=FindingCode.DATE_DIFFERENCE, what="x", finding_id="legacy")
    ] if outcome == PrecheckOutcome.DISCREPANCIES_FOUND else []
    return build_recommendation_card(
        comparison_status=comparison,
        next_action=next_action,
        findings=dummy,
        already_ordered_or_paid=already_ordered_or_paid,
        client_declined_offer=False,
        catalog_amount_rub=catalog_amount_rub,
        catalog_label=catalog_label,
        package_code=package_code,
    )
