"""Оркестратор AI-пайплайна кейса: intake → … → human_review."""

from __future__ import annotations

from dataclasses import dataclass, field

from sfrfr.ai.agents.classifier import classify_document
from sfrfr.ai.agents.drafter import draft_application
from sfrfr.ai.agents.extractor import extract_periods
from sfrfr.ai.llm import LLMClient
from sfrfr.ai.schemas.agents import (
    ClassifyResult,
    DocumentType,
    DraftResult,
    ExtractResult,
    Finding,
)
from sfrfr.core.audit_ils import compare_ils_vs_labor_book
from sfrfr.models.case_status import CaseStatus, next_status
from sfrfr.ocr.engine import extract_texts


@dataclass
class CaseContext:
    """Минимальный контекст кейса для оркестратора (без БД)."""

    case_id: str
    status: CaseStatus = CaseStatus.INTAKE
    client_name: str | None = None
    max_user_id: str | None = None
    max_chat_id: str | None = None
    document_paths: list[str] = field(default_factory=list)
    ocr_texts: list[str] = field(default_factory=list)
    classifications: list[ClassifyResult] = field(default_factory=list)
    ils_periods: list[dict] = field(default_factory=list)
    labor_periods: list[dict] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    draft: DraftResult | None = None
    error: str | None = None


@dataclass
class StepResult:
    ok: bool
    status: CaseStatus
    message: str = ""


class CaseOrchestrator:
    """
    Продвигает кейс по статусам.

    LLM-шаги: classified → extracted → draft_ready.
    Код: ocr_done (внешне), audited (audit_ils), human_review (HITL).
    """

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    def advance(self, ctx: CaseContext) -> StepResult:
        """Выполнить один следующий шаг относительно текущего status."""
        try:
            if ctx.status is CaseStatus.INTAKE:
                return self._to_documents_received(ctx)
            if ctx.status is CaseStatus.DOCUMENTS_RECEIVED:
                return self._mark_ocr_done(ctx)
            if ctx.status is CaseStatus.OCR_DONE:
                return self._classify(ctx)
            if ctx.status is CaseStatus.CLASSIFIED:
                return self._extract(ctx)
            if ctx.status is CaseStatus.EXTRACTED:
                return self._audit(ctx)
            if ctx.status is CaseStatus.AUDITED:
                return self._draft(ctx)
            if ctx.status is CaseStatus.DRAFT_READY:
                return self._to_human_review(ctx)
            if ctx.status is CaseStatus.HUMAN_REVIEW:
                return StepResult(ok=True, status=ctx.status, message="ожидает человека")
            if ctx.status is CaseStatus.COMPLETED:
                return StepResult(ok=True, status=ctx.status, message="кейc завершён")
            if ctx.status is CaseStatus.FAILED:
                return StepResult(ok=False, status=ctx.status, message=ctx.error or "failed")
            return StepResult(
                ok=False,
                status=ctx.status,
                message=f"неизвестный статус: {ctx.status}",
            )
        except Exception as exc:  # noqa: BLE001 — граница оркестратора
            ctx.status = CaseStatus.FAILED
            ctx.error = str(exc)
            return StepResult(ok=False, status=ctx.status, message=str(exc))

    def run_until(
        self,
        ctx: CaseContext,
        *,
        stop_at: CaseStatus = CaseStatus.HUMAN_REVIEW,
        max_steps: int = 16,
    ) -> CaseContext:
        """Крутить advance(), пока не stop_at / FAILED / COMPLETED / тупик."""
        for _ in range(max_steps):
            if ctx.status in (stop_at, CaseStatus.FAILED, CaseStatus.COMPLETED):
                break
            if ctx.status is CaseStatus.HUMAN_REVIEW and stop_at is CaseStatus.HUMAN_REVIEW:
                break
            before = ctx.status
            result = self.advance(ctx)
            if not result.ok or ctx.status is before:
                break
        return ctx

    def complete_after_review(self, ctx: CaseContext) -> StepResult:
        """HITL: юрист подтвердил — completed."""
        if ctx.status is not CaseStatus.HUMAN_REVIEW:
            return StepResult(ok=False, status=ctx.status, message="нужен статус human_review")
        ctx.status = CaseStatus.COMPLETED
        return StepResult(ok=True, status=ctx.status, message="завершено после проверки")

    def _set(self, ctx: CaseContext, status: CaseStatus, message: str) -> StepResult:
        ctx.status = status
        return StepResult(ok=True, status=status, message=message)

    def _to_documents_received(self, ctx: CaseContext) -> StepResult:
        if not ctx.document_paths and not ctx.ocr_texts:
            return StepResult(
                ok=False,
                status=ctx.status,
                message="нет документов: сначала загрузите файлы",
            )
        return self._set(ctx, CaseStatus.DOCUMENTS_RECEIVED, "документы приняты")

    def _mark_ocr_done(self, ctx: CaseContext) -> StepResult:
        if not ctx.ocr_texts and ctx.document_paths:
            ctx.ocr_texts = extract_texts(ctx.document_paths)
        if not ctx.ocr_texts:
            return StepResult(
                ok=False,
                status=ctx.status,
                message="нет OCR-текстов: загрузите документы или передайте текст",
            )
        return self._set(ctx, CaseStatus.OCR_DONE, f"OCR готов: {len(ctx.ocr_texts)} файл(ов)")

    def _classify(self, ctx: CaseContext) -> StepResult:
        ctx.classifications = [
            classify_document(t, client_name=ctx.client_name, llm=self.llm) for t in ctx.ocr_texts
        ]
        return self._set(
            ctx,
            CaseStatus.CLASSIFIED,
            f"классифицировано: {len(ctx.classifications)}",
        )

    def _extract(self, ctx: CaseContext) -> StepResult:
        ils: list[dict] = []
        labor: list[dict] = []
        for text, clf in zip(ctx.ocr_texts, ctx.classifications, strict=False):
            extracted: ExtractResult = extract_periods(
                text, client_name=ctx.client_name, llm=self.llm
            )
            rows = [p.model_dump() for p in extracted.periods]
            if clf.document_type is DocumentType.ILS:
                ils.extend(rows)
            elif clf.document_type is DocumentType.LABOR_BOOK:
                labor.extend(rows)
            else:
                # неизвестный тип — кладём в labor как запасной источник стажа
                labor.extend(rows)
        ctx.ils_periods = ils
        ctx.labor_periods = labor
        return self._set(ctx, CaseStatus.EXTRACTED, "периоды извлечены")

    def _audit(self, ctx: CaseContext) -> StepResult:
        raw = compare_ils_vs_labor_book(ctx.ils_periods, ctx.labor_periods)
        ctx.findings = [
            Finding(type=r.get("type", "unknown"), detail=r.get("detail", "")) for r in raw
        ]
        return self._set(ctx, CaseStatus.AUDITED, f"findings: {len(ctx.findings)}")

    def _draft(self, ctx: CaseContext) -> StepResult:
        ctx.draft = draft_application(
            ctx.findings, client_name=ctx.client_name, llm=self.llm
        )
        return self._set(ctx, CaseStatus.DRAFT_READY, "черновик готов")

    def _to_human_review(self, ctx: CaseContext) -> StepResult:
        return self._set(ctx, CaseStatus.HUMAN_REVIEW, "передано на проверку")


def expected_next(status: CaseStatus) -> CaseStatus | None:
    """Публичная обёртка над next_status для API/CLI."""
    return next_status(status)
