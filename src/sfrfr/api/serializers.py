"""Сборка CaseRead из CaseRecord."""

from __future__ import annotations

from sfrfr.api.schemas.case import CaseRead
from sfrfr.core.case_store import CaseRecord
from sfrfr.models.case_status import STATUS_HINTS_RU, STATUS_LABELS_RU

_SUBMISSION = (
    "Подайте заявление самостоятельно в СФР, через МФЦ или портал Госуслуги. "
    "Сервис SFRFR не подаёт документы от вашего имени."
)
_WARNING = "Решение принимает СФР. Результат не гарантирован."


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
        max_user_id=ctx.max_user_id,
        checklist_items=[],
        next_action="Загрузите ИЛС и трудовую книжку"
        if ctx.status.value == "intake"
        else ("Запустите проверку" if ctx.status.value == "documents_received" else None),
        status_label=STATUS_LABELS_RU.get(ctx.status, ctx.status.value),
        status_hint=STATUS_HINTS_RU.get(ctx.status),
        submission_instruction=_SUBMISSION,
        warning=_WARNING,
    )
