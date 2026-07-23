"""Обратная связь эксперта → обезличенный кейс RAG (ТЗ-08)."""

from __future__ import annotations

from datetime import date

from sfrfr.ai.knowledge.registry import KnowledgeCaseRegistry
from sfrfr.ai.pii.depersonalize import depersonalize_text
from sfrfr.ai.schemas.knowledge_case import (
    ExpertAssessment,
    KnowledgeCase,
    KnowledgeQuality,
    SfrOutcome,
)


def _parse_sfr_outcome(raw: str | None) -> SfrOutcome:
    text = (raw or "").strip().lower()
    if not text:
        return SfrOutcome.UNKNOWN
    if any(x in text for x in ("удовлетв", "granted", "одобр", "учтено")):
        return SfrOutcome.GRANTED
    if any(x in text for x in ("отказ", "denied", "отклон")):
        return SfrOutcome.DENIED
    if any(x in text for x in ("не заверш", "pending", "ожидан", "в работе")):
        return SfrOutcome.PENDING
    return SfrOutcome.UNKNOWN


def _split_notes(raw: str | None) -> list[str]:
    if not raw:
        return []
    cleaned = depersonalize_text(raw).strip()
    if not cleaned:
        return []
    parts = [p.strip(" -•\t") for p in cleaned.replace(";", "\n").splitlines()]
    return [p for p in parts if p][:20]


def _write_companion_md(registry: KnowledgeCaseRegistry, case: KnowledgeCase) -> None:
    """Краткий .md рядом с JSON для чтения человеком."""
    path = registry.cases_dir / f"{case.case_id}.md"
    lines = [
        f"# {case.case_id}",
        "",
        f"- quality: `{case.quality.value}`",
        f"- problem: {case.problem_type or '—'}",
        f"- discrepancy: {case.discrepancy or '—'}",
        f"- sfr_outcome: {case.sfr_outcome.value}",
        f"- documents: {', '.join(case.documents) or '—'}",
        "",
        case.summary or "",
        "",
    ]
    if case.what_worked:
        lines.append("## Что сработало")
        lines.extend(f"- {x}" for x in case.what_worked)
        lines.append("")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def apply_expert_feedback(
    *,
    ops_case_id: str,
    quality: str | KnowledgeQuality,
    what_worked: str | None = None,
    documents_note: str | None = None,
    sfr_outcome: str | None = None,
    problem_type: str | None = None,
    discrepancy: str | None = None,
    registry: KnowledgeCaseRegistry | None = None,
) -> KnowledgeCase:
    """
    Создать/обновить обезличенный CASE-YYYY-NNN по feedback эксперта.
    В RAG попадут только verified/template.
    """
    registry = registry or KnowledgeCaseRegistry()
    q = KnowledgeQuality(quality) if isinstance(quality, str) else quality

    existing = registry.find_by_ops_case_id(ops_case_id)

    worked = _split_notes(what_worked)
    docs = _split_notes(documents_note)
    outcome = _parse_sfr_outcome(sfr_outcome)
    summary_bits = [
        depersonalize_text(what_worked or "").strip(),
        depersonalize_text(documents_note or "").strip(),
        depersonalize_text(sfr_outcome or "").strip(),
    ]
    summary = " | ".join(b for b in summary_bits if b)[:2000]

    if existing is None:
        case = KnowledgeCase(
            case_id=registry.next_case_id(),
            ops_case_id=ops_case_id,
            problem_type=depersonalize_text(problem_type or "expert_feedback").strip()
            or "expert_feedback",
            documents=docs,
            discrepancy=depersonalize_text(discrepancy).strip() if discrepancy else None,
            prepared=[],
            sfr_outcome=outcome,
            expert_assessment=(
                ExpertAssessment.CORRECT
                if q in (KnowledgeQuality.VERIFIED, KnowledgeQuality.TEMPLATE)
                else ExpertAssessment.NEEDS_REWORK
                if q == KnowledgeQuality.DRAFT
                else ExpertAssessment.ERROR
            ),
            quality=q,
            what_worked=worked,
            documents_actually_needed=docs,
            can_be_template=q == KnowledgeQuality.TEMPLATE,
            summary=summary or f"Feedback по операционному делу {ops_case_id[:8]}",
            notes=f"ops_case_id={ops_case_id}",
        )
    else:
        case = existing
        case.quality = q
        case.sfr_outcome = outcome if outcome != SfrOutcome.UNKNOWN else case.sfr_outcome
        if worked:
            case.what_worked = worked
        if docs:
            case.documents_actually_needed = docs
            case.documents = list(dict.fromkeys([*case.documents, *docs]))
        if summary:
            case.summary = summary
        if problem_type:
            case.problem_type = depersonalize_text(problem_type).strip() or case.problem_type
        case.can_be_template = q == KnowledgeQuality.TEMPLATE or case.can_be_template
        case.ops_case_id = ops_case_id

    if q in (KnowledgeQuality.VERIFIED, KnowledgeQuality.TEMPLATE):
        case.verified_at = date.today()
        if q == KnowledgeQuality.TEMPLATE:
            case.can_be_template = True
            case.expert_assessment = ExpertAssessment.CORRECT

    registry.save(case)
    if q in (KnowledgeQuality.VERIFIED, KnowledgeQuality.TEMPLATE):
        _write_companion_md(registry, case)
    return case
