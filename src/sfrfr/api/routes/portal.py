"""Защищённые API для client и admin кабинетов."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from sfrfr.api.schemas.portal import (
    CaseMessageCreate,
    CaseStatusUpdate,
    CaseSummary,
    SignedDocumentResponse,
)
from sfrfr.db.case_repository import CaseRepository
from sfrfr.db.session import get_supabase_client
from sfrfr.security.auth import Principal, StaffRole, get_current_principal, require_staff

router = APIRouter()

_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
}
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _repo() -> CaseRepository:
    return CaseRepository()


def _summary(case: dict) -> CaseSummary:
    checklist = case.get("checklist_items") or []
    return CaseSummary(
        id=str(case["id"]),
        pipeline_status=case["pipeline_status"],
        b2c_status=case["b2c_status"],
        created_at=case.get("created_at"),
        expert_user_id=str(case["expert_user_id"]) if case.get("expert_user_id") else None,
        checklist_open_count=sum(1 for item in checklist if item.get("status") != "done"),
    )


@router.get("/me/cases", response_model=list[CaseSummary])
def list_my_cases(
    principal: Principal = Depends(get_current_principal),
) -> list[CaseSummary]:
    """Клиент видит свои дела, сотрудник — дела по своей роли."""
    return [_summary(case) for case in _repo().list_cases(principal)]


@router.get("/cases/{case_id}")
def get_case(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    case = _repo().require_case(principal, case_id)
    _repo().audit(case_id, principal.user_id, "case_viewed")
    return case


@router.post("/cases/{case_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_case_document(
    case_id: str,
    file: UploadFile = File(...),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    """Загрузить разрешённый файл в private bucket через доверенный API."""
    repo = _repo()
    repo.require_case(principal, case_id)

    content_type = file.content_type or ""
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="unsupported document type")

    data = await file.read(_MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="document exceeds 50 MiB")

    filename = Path(file.filename or "document").name
    document_id = str(uuid4())
    storage_path = f"{case_id}/{document_id}/{filename}"
    client = get_supabase_client()
    client.storage.from_("pension-docs").upload(
        storage_path,
        data,
        {"content-type": content_type, "x-upsert": "false"},
    )
    response = (
        client.table("documents")
        .insert(
            {
                "id": document_id,
                "case_id": case_id,
                "storage_path": storage_path,
                "doc_type": None,
                "uploaded_by": principal.user_id,
            }
        )
        .execute()
    )
    repo.audit(case_id, principal.user_id, "document_uploaded")
    return response.data[0]


@router.post(
    "/cases/{case_id}/documents/{document_id}/signed-url",
    response_model=SignedDocumentResponse,
)
def create_document_signed_url(
    case_id: str,
    document_id: str,
    principal: Principal = Depends(get_current_principal),
) -> SignedDocumentResponse:
    """Выдать краткоживущую ссылку после проверки доступа к делу."""
    repo = _repo()
    repo.require_case(principal, case_id)
    row = (
        get_supabase_client()
        .table("documents")
        .select("storage_path")
        .eq("id", document_id)
        .eq("case_id", case_id)
        .maybe_single()
        .execute()
        .data
    )
    if not row:
        raise HTTPException(status_code=404, detail="document not found")

    expires_in = 60
    signed = get_supabase_client().storage.from_("pension-docs").create_signed_url(
        row["storage_path"], expires_in
    )
    repo.audit(case_id, principal.user_id, "document_download_url_created")
    return SignedDocumentResponse(url=signed["signedURL"], expires_in=expires_in)


@router.get("/cases/{case_id}/messages")
def list_messages(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> list[dict]:
    _repo().require_case(principal, case_id)
    return (
        get_supabase_client()
        .table("case_messages")
        .select("*")
        .eq("case_id", case_id)
        .order("created_at")
        .execute()
        .data
        or []
    )


@router.post("/cases/{case_id}/messages", status_code=status.HTTP_201_CREATED)
def create_message(
    case_id: str,
    payload: CaseMessageCreate,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    repo = _repo()
    repo.require_case(principal, case_id)
    kind = "staff" if principal.is_staff else "client"
    response = (
        get_supabase_client()
        .table("case_messages")
        .insert(
            {
                "case_id": case_id,
                "author_user_id": principal.user_id,
                "author_kind": kind,
                "body": payload.body,
            }
        )
        .execute()
    )
    repo.audit(case_id, principal.user_id, "message_created")
    return response.data[0]


@router.patch("/admin/cases/{case_id}/pipeline-status", response_model=CaseSummary)
def update_pipeline_status(
    case_id: str,
    payload: CaseStatusUpdate,
    principal: Principal = Depends(require_staff),
) -> CaseSummary:
    """Изменение pipeline доступно только сотруднику с правом на дело."""
    repo = _repo()
    case = repo.require_case(principal, case_id)
    if principal.role is StaffRole.OPERATOR:
        raise HTTPException(status_code=403, detail="expert or admin role required")
    repo.update_case_status(case_id, payload.pipeline_status.value, principal.user_id)
    case["pipeline_status"] = payload.pipeline_status.value
    return _summary(case)
