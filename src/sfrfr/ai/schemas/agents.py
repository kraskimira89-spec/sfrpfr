"""Pydantic-схемы входов/выходов AI-агентов."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class DocumentType(StrEnum):
    ILS = "ils"
    LABOR_BOOK = "labor_book"
    PASSPORT = "passport"
    APPLICATION = "application"
    OTHER = "other"


class Period(BaseModel):
    employer: str | None = None
    date_from: str | None = Field(default=None, description="YYYY-MM-DD или как в документе")
    date_to: str | None = None
    source: DocumentType | None = None


class ClassifyResult(BaseModel):
    document_type: DocumentType
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    notes: str | None = None


class ExtractResult(BaseModel):
    periods: list[Period] = Field(default_factory=list)
    raw_hints: list[str] = Field(default_factory=list)


class Finding(BaseModel):
    type: str
    detail: str
    severity: str = "info"


class DraftResult(BaseModel):
    title: str
    body: str
    findings_used: list[str] = Field(default_factory=list)
    needs_human_review: bool = True


class KnowledgeHit(BaseModel):
    source: str
    snippet: str
    score: float = 0.0
