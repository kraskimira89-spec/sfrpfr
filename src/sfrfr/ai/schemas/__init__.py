"""Схемы AI-агентов и базы знаний."""

from sfrfr.ai.schemas.agents import (
    ClassifyResult,
    DocumentType,
    DraftResult,
    ExtractResult,
    Finding,
    KnowledgeHit,
    Period,
)
from sfrfr.ai.schemas.knowledge_case import (
    ExpertAssessment,
    KnowledgeCase,
    KnowledgeQuality,
    RAG_READY_QUALITIES,
    SfrOutcome,
)

__all__ = [
    "ClassifyResult",
    "DocumentType",
    "DraftResult",
    "ExpertAssessment",
    "ExtractResult",
    "Finding",
    "KnowledgeCase",
    "KnowledgeHit",
    "KnowledgeQuality",
    "Period",
    "RAG_READY_QUALITIES",
    "SfrOutcome",
]
