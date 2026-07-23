"""Защищённые API для client и admin кабинетов."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from sfrfr.api.schemas.portal import (
    CaseMessageCreate,
    CaseStatusUpdate,
    CaseSummary,
    ClientCaseDetail,
    ConsentAcceptRequest,
    ContractAcceptRequest,
    SignedDocumentResponse,
)
from sfrfr.core.config import get_settings
from sfrfr.core.success_fee import calc_success_fee
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

_SUBMISSION_INSTRUCTION = (
    "Подайте заявление самостоятельно в СФР, через МФЦ или портал Госуслуги. "
    "Сервис SFRFR не подаёт документы от вашего имени. "
    "Используйте черновик заявления и чек-лист как подсказку — решение принимает СФР."
)

_SFR_WARNING = "Решение принимает СФР. Результат не гарантирован."


def _repo() -> CaseRepository:
    return CaseRepository()


def _summary(case: dict, *, unread: int = 0, consent_accepted: bool = False) -> CaseSummary:
    checklist = case.get("checklist_items") or []
    return CaseSummary(
        id=str(case["id"]),
        pipeline_status=case["pipeline_status"],
        b2c_status=case["b2c_status"],
        created_at=case.get("created_at"),
        expert_user_id=str(case["expert_user_id"]) if case.get("expert_user_id") else None,
        expert_assigned=bool(case.get("expert_user_id")),
        checklist_open_count=sum(1 for item in checklist if item.get("status") != "done"),
        next_action=CaseRepository.next_client_action(case),
        unread_messages=unread,
        consent_accepted=consent_accepted,
    )


def _client_detail(case: dict, *, consent_accepted: bool, draft: dict | None) -> ClientCaseDetail:
    return ClientCaseDetail(
        id=str(case["id"]),
        pipeline_status=case["pipeline_status"],
        b2c_status=case["b2c_status"],
        created_at=case.get("created_at"),
        expert_assigned=bool(case.get("expert_user_id")),
        consent_accepted=consent_accepted,
        checklist_items=list(case.get("checklist_items") or []),
        required_documents=CaseRepository.required_document_items(case),
        documents=list(case.get("documents") or []),
        draft=draft,
        submission_instruction=_SUBMISSION_INSTRUCTION,
        warning=_SFR_WARNING,
    )


def _require_consent_for_upload(repo: CaseRepository, case_id: str) -> None:
    if get_settings().require_consent and not repo.has_consent(case_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="consent required before document upload",
        )


@router.get("/me/cases", response_model=list[CaseSummary])
def list_my_cases(
    principal: Principal = Depends(get_current_principal),
) -> list[CaseSummary]:
    """Клиент видит свои дела, сотрудник — дела по своей роли."""
    repo = _repo()
    summaries: list[CaseSummary] = []
    for case in repo.list_cases(principal):
        case_id = str(case["id"])
        unread = 0 if principal.is_staff else repo.unread_staff_messages(case_id, principal.user_id)
        summaries.append(
            _summary(
                case,
                unread=unread,
                consent_accepted=repo.has_consent(case_id),
            )
        )
    return summaries


@router.get("/cases/{case_id}")
def get_case(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    repo = _repo()
    case = repo.require_case(principal, case_id)
    repo.audit(case_id, principal.user_id, "case_viewed")
    if principal.is_staff:
        pipeline = (
            get_supabase_client()
            .table("case_pipeline_data")
            .select("*")
            .eq("case_id", case_id)
            .maybe_single()
            .execute()
            .data
        )
        case["pipeline_data"] = pipeline
        return case

    detail = _client_detail(
        case,
        consent_accepted=repo.has_consent(case_id),
        draft=repo.get_pipeline_draft(case_id),
    )
    return detail.model_dump(mode="json")


@router.post("/cases/{case_id}/consents", status_code=status.HTTP_201_CREATED)
def accept_consent(
    case_id: str,
    payload: ConsentAcceptRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    repo = _repo()
    repo.require_case(principal, case_id)
    if principal.is_staff:
        raise HTTPException(status_code=403, detail="client or representative only")
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else None
    return repo.accept_consent(
        case_id,
        version=payload.version,
        actor_id=principal.user_id,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/cases/{case_id}/consents")
def list_consents(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    repo = _repo()
    repo.require_case(principal, case_id)
    return {
        "consents": repo.list_consents(case_id),
        "contract_acceptances": repo.list_contract_acceptances(case_id),
        "offer_url": "https://taxi-doroga-dobra.ru/oferta/",
        "pdn_url": "https://taxi-doroga-dobra.ru/politika-pdn/",
        "consent_url": "https://taxi-doroga-dobra.ru/soglasie/",
    }


@router.post("/cases/{case_id}/contract-acceptances", status_code=status.HTTP_201_CREATED)
def accept_contract(
    case_id: str,
    payload: ContractAcceptRequest,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    repo = _repo()
    repo.require_case(principal, case_id)
    if principal.is_staff:
        raise HTTPException(status_code=403, detail="client or representative only")
    return repo.accept_contract(
        case_id,
        offer_version=payload.offer_version,
        actor_id=principal.user_id,
        order_id=payload.order_id,
        meta={"accepted_by": principal.user_id},
    )


@router.get("/cases/{case_id}/orders")
def list_orders(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> list[dict]:
    repo = _repo()
    repo.require_case(principal, case_id)
    return repo.list_orders(case_id)


@router.get("/cases/{case_id}/result")
def get_result(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    repo = _repo()
    repo.require_case(principal, case_id)
    evidence = repo.get_result_evidence(case_id) or {}
    before = float(evidence.get("monthly_before_rub") or 0)
    after = float(evidence.get("monthly_after_rub") or 0)
    lump = float(evidence.get("lump_sum_rub") or 0)
    fee = calc_success_fee(lump_sum_rub=lump, monthly_increase_rub=max(after - before, 0))
    return {
        "evidence": evidence or None,
        "success_fee": fee,
        "post_payment_note": (
            "Счёт post-payment выставляется только после подтверждения результата экспертом "
            "и по истечении окна ожидания 2–3 месяца."
        ),
        "warning": _SFR_WARNING,
    }


@router.post("/cases/{case_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_case_document(
    case_id: str,
    file: UploadFile = File(...),
    doc_type: str | None = Form(default=None),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    """Загрузить разрешённый файл в private bucket через доверенный API."""
    repo = _repo()
    repo.require_case(principal, case_id)
    if not principal.is_staff:
        _require_consent_for_upload(repo, case_id)

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
                "doc_type": doc_type,
                "uploaded_by": principal.user_id,
            }
        )
        .execute()
    )
    action = "result_decision_uploaded" if doc_type == "sfr_decision" else "document_uploaded"
    repo.audit(case_id, principal.user_id, action)
    if doc_type == "sfr_decision":
        client.table("cases").update({"b2c_status": "result_pending"}).eq("id", case_id).execute()
        existing = repo.get_result_evidence(case_id)
        if existing:
            client.table("result_evidence").update({"document_id": document_id}).eq(
                "id", existing["id"]
            ).execute()
        else:
            client.table("result_evidence").insert(
                {"case_id": case_id, "document_id": document_id}
            ).execute()
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
    return _summary(case, consent_accepted=repo.has_consent(case_id))
