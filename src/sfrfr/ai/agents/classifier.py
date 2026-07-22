"""Агент: классификация типа документа."""

from __future__ import annotations

from sfrfr.ai.guardrails import redact_for_llm
from sfrfr.ai.llm import LLMClient
from sfrfr.ai.prompts import CLASSIFY_SYSTEM
from sfrfr.ai.schemas.agents import ClassifyResult, DocumentType

_HEURISTICS: list[tuple[tuple[str, ...], DocumentType]] = [
    (("илс", "индивидуальн", "лицевой счет", "сфр"), DocumentType.ILS),
    (("трудов", "книжк", "стаж"), DocumentType.LABOR_BOOK),
    (("паспорт", "серия", "выдан"), DocumentType.PASSPORT),
    (("заявлен", "прошу"), DocumentType.APPLICATION),
]


def classify_document(
    text: str,
    *,
    client_name: str | None = None,
    llm: LLMClient | None = None,
) -> ClassifyResult:
    """Классификация: эвристика → опционально LLM."""
    safe = redact_for_llm(text, client_name=client_name)
    lowered = safe.lower()

    for keys, doc_type in _HEURISTICS:
        if any(k in lowered for k in keys):
            return ClassifyResult(document_type=doc_type, confidence=0.7, notes="heuristic")

    llm = llm or LLMClient()
    if llm.available:
        raw = llm.chat(system=CLASSIFY_SYSTEM, user=safe[:4000]).lower().strip()
        for doc_type in DocumentType:
            if doc_type.value in raw:
                return ClassifyResult(document_type=doc_type, confidence=0.6, notes="llm")

    return ClassifyResult(document_type=DocumentType.OTHER, confidence=0.2, notes="fallback")
