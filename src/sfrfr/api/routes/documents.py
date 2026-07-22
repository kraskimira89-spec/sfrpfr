from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from sfrfr.api.schemas.case import CaseRead
from sfrfr.api.serializers import case_to_read
from sfrfr.core.case_store import get_case_store
from sfrfr.storage.local import save_upload

router = APIRouter()


@router.post("/upload", response_model=CaseRead)
async def upload_document(
    case_id: str = Form(...),
    file: UploadFile = File(...),
) -> CaseRead:
    """Загрузка скана/PDF/txt в карточку дела → local storage + статус documents_received."""
    store = get_case_store()
    try:
        store.require(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="case not found") from exc

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")

    path = save_upload(case_id, file.filename or "upload.bin", data)
    record = store.add_document(case_id, str(path))
    return case_to_read(record)
