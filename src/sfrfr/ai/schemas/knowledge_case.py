"""Схемы обезличенных кейсов базы знаний (RAG)."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class KnowledgeQuality(StrEnum):
    DRAFT = "draft"
    VERIFIED = "verified"
    REJECTED = "rejected"
    TEMPLATE = "template"


class SfrOutcome(StrEnum):
    GRANTED = "granted"
    DENIED = "denied"
    PENDING = "pending"
    UNKNOWN = "unknown"


class ExpertAssessment(StrEnum):
    CORRECT = "correct"
    ERROR = "error"
    NEEDS_REWORK = "needs_rework"
    UNKNOWN = "unknown"


# Только эти статусы попадают в RAG.
RAG_READY_QUALITIES: frozenset[KnowledgeQuality] = frozenset(
    {KnowledgeQuality.VERIFIED, KnowledgeQuality.TEMPLATE}
)


class KnowledgeCase(BaseModel):
    """Обезличенный кейс для реестра и RAG."""

    case_id: str = Field(description="CASE-YYYY-NNN")
    problem_type: str = ""
    documents: list[str] = Field(default_factory=list)
    discrepancy: str | None = None
    legal_basis: str | None = None
    prepared: list[str] = Field(default_factory=list)
    sfr_outcome: SfrOutcome = SfrOutcome.UNKNOWN
    pension_increase_range: str | None = None
    edv_range: str | None = None
    expert_assessment: ExpertAssessment = ExpertAssessment.UNKNOWN
    verified_at: date | None = None
    quality: KnowledgeQuality = KnowledgeQuality.DRAFT
    what_worked: list[str] = Field(default_factory=list)
    what_failed: list[str] = Field(default_factory=list)
    documents_actually_needed: list[str] = Field(default_factory=list)
    can_be_template: bool = False
    source_file: str | None = None
    notes: str | None = None
    summary: str = ""

    def is_rag_ready(self) -> bool:
        return self.quality in RAG_READY_QUALITIES

    def rag_text(self) -> str:
        """Текст для keyword/embedding поиска (без ПДн)."""
        parts = [
            self.case_id,
            self.problem_type,
            self.discrepancy or "",
            self.legal_basis or "",
            self.summary,
            " ".join(self.documents),
            " ".join(self.prepared),
            " ".join(self.what_worked),
            f"sfr:{self.sfr_outcome.value}",
        ]
        return " ".join(p for p in parts if p).strip()
