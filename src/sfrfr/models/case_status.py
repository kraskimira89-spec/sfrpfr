"""Статусы пенсионного кейса (MVP pipeline)."""

from __future__ import annotations

from enum import StrEnum


class CaseStatus(StrEnum):
    """Жизненный цикл кейса: intake → … → completed."""

    INTAKE = "intake"
    DOCUMENTS_RECEIVED = "documents_received"
    OCR_DONE = "ocr_done"
    CLASSIFIED = "classified"
    EXTRACTED = "extracted"
    AUDITED = "audited"
    DRAFT_READY = "draft_ready"
    HUMAN_REVIEW = "human_review"
    COMPLETED = "completed"
    FAILED = "failed"


# Линейный happy-path (без FAILED)
PIPELINE_ORDER: tuple[CaseStatus, ...] = (
    CaseStatus.INTAKE,
    CaseStatus.DOCUMENTS_RECEIVED,
    CaseStatus.OCR_DONE,
    CaseStatus.CLASSIFIED,
    CaseStatus.EXTRACTED,
    CaseStatus.AUDITED,
    CaseStatus.DRAFT_READY,
    CaseStatus.HUMAN_REVIEW,
    CaseStatus.COMPLETED,
)


def next_status(current: CaseStatus) -> CaseStatus | None:
    """Следующий статус по happy-path или None, если конец / FAILED."""
    if current is CaseStatus.FAILED:
        return None
    try:
        idx = PIPELINE_ORDER.index(current)
    except ValueError:
        return None
    if idx + 1 >= len(PIPELINE_ORDER):
        return None
    return PIPELINE_ORDER[idx + 1]
