"""unit-тесты оркестратора и статусов кейса."""

from sfrfr.ai.orchestrator import CaseContext, CaseOrchestrator
from sfrfr.models.case_status import PIPELINE_ORDER, CaseStatus, next_status


def test_pipeline_order_starts_at_intake() -> None:
    assert PIPELINE_ORDER[0] is CaseStatus.INTAKE
    assert next_status(CaseStatus.INTAKE) is CaseStatus.DOCUMENTS_RECEIVED
    assert next_status(CaseStatus.COMPLETED) is None
    assert next_status(CaseStatus.FAILED) is None


def test_orchestrator_reaches_human_review_without_llm() -> None:
    ctx = CaseContext(
        case_id="demo",
        client_name="Иванов Иван",
        ocr_texts=[
            "Выписка из ИЛС СФР, индивидуальный лицевой счет",
            "Трудовая книжка: стаж с 01.01.2010 по 31.12.2015 ООО Ромашка",
        ],
    )
    orch = CaseOrchestrator()
    orch.run_until(ctx, stop_at=CaseStatus.HUMAN_REVIEW)

    assert ctx.status is CaseStatus.HUMAN_REVIEW
    assert ctx.draft is not None
    assert ctx.draft.needs_human_review is True
    assert len(ctx.classifications) == 2


def test_complete_after_review() -> None:
    ctx = CaseContext(case_id="x", status=CaseStatus.HUMAN_REVIEW)
    result = CaseOrchestrator().complete_after_review(ctx)
    assert result.ok is True
    assert ctx.status is CaseStatus.COMPLETED
