"""Сборка CaseRead из CaseRecord."""

from __future__ import annotations

from sfrfr.api.schemas.case import CaseRead
from sfrfr.core.case_store import CaseRecord


def case_to_read(record: CaseRecord) -> CaseRead:
    ctx = record.ctx
    return CaseRead(
        id=record.case_id,
        client_name=record.client_name,
        snils_masked=record.snils_masked,
        status=ctx.status,
        document_count=len(ctx.document_paths),
        ocr_count=len(ctx.ocr_texts),
        findings=list(ctx.findings),
        draft=ctx.draft,
        error=ctx.error,
    )
