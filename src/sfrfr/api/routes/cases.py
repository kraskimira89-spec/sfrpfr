from fastapi import APIRouter, HTTPException, Query

from sfrfr.api.schemas.case import AdvanceResponse, CaseCreate, CaseRead
from sfrfr.api.serializers import case_to_read
from sfrfr.core.case_store import get_case_store
from sfrfr.models.case_status import CaseStatus

router = APIRouter()


@router.post("", response_model=CaseRead)
def create_case(payload: CaseCreate) -> CaseRead:
    """Создать карточку пенсионного дела (in-memory)."""
    store = get_case_store()
    record = store.create(
        client_name=payload.client_name,
        snils_masked=payload.snils_masked,
        consent_given=payload.consent_given,
    )
    return case_to_read(record)


@router.get("/{case_id}", response_model=CaseRead)
def get_case(case_id: str) -> CaseRead:
    store = get_case_store()
    try:
        record = store.require(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="case not found") from exc
    return case_to_read(record)


@router.post("/{case_id}/advance", response_model=AdvanceResponse)
def advance_case(case_id: str) -> AdvanceResponse:
    """Один шаг пайплайна (включая OCR при documents_received)."""
    store = get_case_store()
    try:
        record, result = store.advance(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="case not found") from exc
    return AdvanceResponse(ok=result.ok, message=result.message, case=case_to_read(record))


@router.post("/{case_id}/run", response_model=CaseRead)
def run_case(
    case_id: str,
    stop_at: CaseStatus = Query(default=CaseStatus.HUMAN_REVIEW),
) -> CaseRead:
    """Прогнать пайплайн до stop_at (по умолчанию human_review)."""
    store = get_case_store()
    try:
        store.require(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="case not found") from exc
    record = store.run_until(case_id, stop_at=stop_at)
    return case_to_read(record)


@router.post("/{case_id}/complete", response_model=AdvanceResponse)
def complete_case(case_id: str) -> AdvanceResponse:
    """HITL: завершить после human_review."""
    store = get_case_store()
    try:
        record, result = store.complete(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="case not found") from exc
    return AdvanceResponse(ok=result.ok, message=result.message, case=case_to_read(record))
