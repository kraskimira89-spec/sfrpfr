"""Сведения и расхождения: строгая schema, цитаты с document_id, без выдумок.

Нормализует legacy findings пайплайна. Не изобретает факты без источника.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

ReviewStatus = Literal["draft", "needs_review", "confirmed", "corrected", "rejected"]


class FactCitation(BaseModel):
    document_id: str | None = None
    quote: str = ""
    page: int | None = None
    paragraph: str | None = None
    label: str | None = None  # ils / labor / other


class CaseDiscrepancy(BaseModel):
    id: str
    type: str
    summary: str
    severity: str = "info"
    left: FactCitation | None = None
    right: FactCitation | None = None
    status: ReviewStatus = "draft"
    needs_specialist: bool = True
    # HITL
    original_summary: str | None = None
    correction: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None


class CaseFactsBundle(BaseModel):
    discrepancies: list[CaseDiscrepancy] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    fingerprint: str = ""
    invented: bool = False  # всегда False — маркер «не выдумывали»


_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _stable_id(*parts: str) -> str:
    blob = "|".join(parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _extract_doc_id(text: str) -> str | None:
    m = _UUID_RE.search(text or "")
    return m.group(0) if m else None


def normalize_findings_to_discrepancies(
    findings: list[dict[str, Any]] | None,
    *,
    documents: list[dict[str, Any]] | None = None,
    reviews: dict[str, dict[str, Any]] | None = None,
) -> CaseFactsBundle:
    """Преобразовать сырые findings → строгие расхождения. Без invent."""
    docs = documents or []
    doc_ids = {str(d.get("id") or "") for d in docs if d.get("id")}
    reviews = reviews or {}
    out: list[CaseDiscrepancy] = []
    for raw in findings or []:
        if not isinstance(raw, dict):
            continue
        ftype = str(raw.get("type") or "info").strip() or "info"
        detail = str(raw.get("detail") or "").strip()
        if not detail and not ftype:
            continue
        # Не выдумываем quote/page — только если уже есть в raw
        left = None
        right = None
        src_doc = raw.get("document_id") or raw.get("source_document_id")
        quote = str(raw.get("quote") or raw.get("citation") or "").strip()
        page = raw.get("page")
        page_i = int(page) if isinstance(page, int) or (isinstance(page, str) and page.isdigit()) else None
        if src_doc or quote or page_i is not None:
            doc_id = str(src_doc).strip() if src_doc else _extract_doc_id(detail)
            if doc_id and doc_id not in doc_ids and doc_ids:
                # Ссылка на чужой/несуществующий doc — не подставляем выдуманный id
                doc_id = None
            left = FactCitation(
                document_id=doc_id,
                quote=quote[:500] if quote else detail[:200],
                page=page_i,
                paragraph=str(raw.get("paragraph") or "") or None,
                label=str(raw.get("source_label") or "") or None,
            )
        # Второй источник — только если явно в raw
        if raw.get("other_document_id") or raw.get("other_quote"):
            other_id = str(raw.get("other_document_id") or "").strip() or None
            if other_id and other_id not in doc_ids and doc_ids:
                other_id = None
            right = FactCitation(
                document_id=other_id,
                quote=str(raw.get("other_quote") or "")[:500],
                page=int(raw["other_page"]) if isinstance(raw.get("other_page"), int) else None,
                paragraph=str(raw.get("other_paragraph") or "") or None,
                label=str(raw.get("other_label") or "") or None,
            )

        did = str(raw.get("id") or "") or _stable_id(ftype, detail)
        review = reviews.get(did) or {}
        status: ReviewStatus = "needs_review"
        if review.get("status") in {"confirmed", "corrected", "rejected", "draft", "needs_review"}:
            status = review["status"]  # type: ignore[assignment]
        elif raw.get("status") in {"confirmed", "corrected", "rejected", "draft", "needs_review"}:
            status = raw["status"]  # type: ignore[assignment]

        item = CaseDiscrepancy(
            id=did,
            type=ftype,
            summary=detail or ftype,
            severity=str(raw.get("severity") or "info"),
            left=left,
            right=right,
            status=status,
            needs_specialist=status in {"needs_review", "draft"},
            original_summary=review.get("original_summary") or detail or ftype,
            correction=review.get("correction"),
            reviewed_by=review.get("reviewed_by"),
            reviewed_at=review.get("reviewed_at"),
        )
        out.append(item)

    missing: list[str] = []
    # Не выдумываем missing из воздуха — только явные типы
    for item in out:
        if item.type in {"missing_in_ils", "missing_labor_book"} and item.summary:
            missing.append(item.summary)

    fp_parts = [f"{d.id}:{d.status}:{d.summary}" for d in out]
    fingerprint = hashlib.sha256("|".join(fp_parts).encode("utf-8")).hexdigest()[:24]
    return CaseFactsBundle(
        discrepancies=out,
        missing=missing,
        fingerprint=fingerprint,
        invented=False,
    )


def apply_specialist_review(
    bundle: CaseFactsBundle,
    *,
    discrepancy_id: str,
    status: ReviewStatus,
    correction: str | None,
    actor_id: str,
    reviewed_at: str,
) -> CaseFactsBundle:
    """Сохранить исход/исправление/автора; без смены чужих id."""
    updated: list[CaseDiscrepancy] = []
    for item in bundle.discrepancies:
        if item.id != discrepancy_id:
            updated.append(item)
            continue
        original = item.original_summary or item.summary
        new_summary = (correction or "").strip() if status == "corrected" else item.summary
        if status == "corrected" and not new_summary:
            new_summary = item.summary
        updated.append(
            item.model_copy(
                update={
                    "status": status,
                    "summary": new_summary if status == "corrected" else item.summary,
                    "original_summary": original,
                    "correction": (correction or "").strip() or None,
                    "reviewed_by": actor_id,
                    "reviewed_at": reviewed_at,
                    "needs_specialist": status in {"needs_review", "draft"},
                }
            )
        )
    fp_parts = [f"{d.id}:{d.status}:{d.summary}" for d in updated]
    fingerprint = hashlib.sha256("|".join(fp_parts).encode("utf-8")).hexdigest()[:24]
    return CaseFactsBundle(
        discrepancies=updated,
        missing=list(bundle.missing),
        fingerprint=fingerprint,
        invented=False,
    )


def pending_specialist_questions(bundle: CaseFactsBundle) -> list[str]:
    """Только конкретные вопросы по needs_review — не общие «нужна проверка»."""
    questions: list[str] = []
    for d in bundle.discrepancies:
        if d.status not in {"needs_review", "draft"}:
            continue
        cite = ""
        if d.left and d.left.document_id:
            cite = f" (док. {d.left.document_id[:8]}"
            if d.left.page is not None:
                cite += f", стр. {d.left.page}"
            cite += ")"
        questions.append(f"Сверьте: {d.summary}{cite}")
    return questions


def new_review_id() -> str:
    return str(uuid4())
