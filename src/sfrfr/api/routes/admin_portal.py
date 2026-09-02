"""Admin/expert API: дашборд, реестр, карточка, финансы, роли (ТЗ-04 + каналы ТЗ-09)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
)

from sfrfr.api.routes.portal import _client_documents
from sfrfr.api.schemas.admin import (
    AssignExpertRequest,
    CancelOrderRequest,
    CaseArchivePrepUpdate,
    CaseCloseRequest,
    CaseFlagsUpdate,
    CaseNextActionUpdate,
    ChecklistItemCreate,
    ChecklistItemUpdate,
    DashboardResponse,
    DiagnosisPublishRequest,
    FinancePayLinkRequest,
    FinanceRemindRequest,
    KnowledgeFeedbackRequest,
    ManualPaymentRequest,
    MaxReplyRequest,
    NotificationJobApproveRequest,
    OrderCreateRequest,
    ResultConfirmRequest,
    StaffCaseSummary,
    StaffInviteRequest,
    StaffPatchRequest,
    StaffRoleUpsert,
    SurveyCampaignApproveRequest,
    SurveyCampaignRescheduleRequest,
    TrackerQualityIssueRequest,
    WorkQueueItem,
    YandexMailRequest,
)
from sfrfr.api.schemas.portal import CaseStatusUpdate, CaseSummary
from sfrfr.core.config import get_settings
from sfrfr.core.success_fee import (
    SUCCESS_FEE_DELAY_DAYS_MIN,
    calc_success_fee,
)
from sfrfr.db.case_repository import CaseRepository
from sfrfr.db.session import get_supabase_client
from sfrfr.integrations.amocrm.sync import persist_crm_external_id, push_case_to_amocrm
from sfrfr.integrations.amocrm.urls import (
    admin_case_max_reply_url,
    max_business_dialogs_url,
    staff_max_login_url,
)
from sfrfr.security.auth import (
    Principal,
    StaffRole,
    require_admin,
    require_staff,
)
from sfrfr.security.integrations import PRIVATE_STORAGE_BUCKET
from sfrfr.services.admin_analytics import (
    analytics_export_rows,
    build_admin_analytics,
    rows_to_csv,
    rows_to_json,
)
from sfrfr.services.case_message_text import strip_internal_staff_prefix
from sfrfr.services.document_ingest_worker import (
    enqueue_document_ingest_job,
)
from sfrfr.services.public_tariffs import staff_package_label
from sfrfr.services.staff_finance import (
    build_finance_snapshot,
    derive_finance_attention,
    reminder_draft_text,
    serialize_order,
)
from sfrfr.services.staff_next_action_ai import suggest_next_action
from sfrfr.services.staff_reply_suggest import suggest_staff_replies
from sfrfr.services.staff_work_queue import (
    build_dashboard_snapshot,
    build_work_item,
    derive_next_action,
    derive_waiting_on,
    is_test_case,
)

router = APIRouter()

def _repo() -> CaseRepository:
    return CaseRepository()


def _require_expert(principal: Principal) -> Principal:
    if principal.role not in (StaffRole.EXPERT, StaffRole.ADMIN):
        raise HTTPException(status_code=403, detail="expert or admin role required")
    return principal


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _silent_days(case: dict[str, Any]) -> int:
    anchor = _parse_dt(case.get("first_contact_at")) or _parse_dt(case.get("created_at"))
    if not anchor:
        return 0
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=UTC)
    return max(0, (datetime.now(UTC) - anchor).days)


def _crm_url(crm_external_id: str | None) -> str | None:
    if not crm_external_id:
        return None
    settings = get_settings()
    subdomain = (settings.amo_subdomain or "").strip()
    if not subdomain:
        return None
    template = settings.amo_case_url_template or (
        "https://{subdomain}.amocrm.ru/leads/detail/{id}"
    )
    return template.replace("{subdomain}", subdomain).replace("{id}", str(crm_external_id))


def _push_case_crm(case: dict[str, Any], *, task: str | None = None) -> None:
    """Неблокирующий sync в amoCRM."""
    amo = push_case_to_amocrm(case, task=task)
    lead_id = amo.get("lead_id") if isinstance(amo, dict) else None
    if lead_id and amo.get("ok") and not case.get("crm_external_id"):
        persist_crm_external_id(str(case.get("id") or ""), str(lead_id))
        case["crm_external_id"] = str(lead_id)


def _staff_summary(case: dict[str, Any], *, role: StaffRole | None) -> StaffCaseSummary:
    client = case.get("clients") or {}
    checklist = case.get("checklist_items") or []
    orders = case.get("orders") or []
    show_contact = role in (StaffRole.OPERATOR, StaffRole.ADMIN, StaffRole.EXPERT)
    work = build_work_item(case, show_contact=show_contact)
    return StaffCaseSummary(
        id=str(case["id"]),
        pipeline_status=case["pipeline_status"],
        b2c_status=case["b2c_status"],
        created_at=case.get("created_at"),
        first_contact_at=case.get("first_contact_at"),
        expert_user_id=str(case["expert_user_id"]) if case.get("expert_user_id") else None,
        checklist_open_count=sum(1 for item in checklist if item.get("status") != "done"),
        client_name=client.get("full_name") if show_contact else None,
        client_phone=client.get("phone") if show_contact else None,
        crm_external_id=case.get("crm_external_id"),
        crm_url=_crm_url(case.get("crm_external_id")),
        meeting_url=case.get("meeting_url"),
        preferred_channel=client.get("preferred_channel") or "unset",
        max_linked=bool(client.get("max_user_id")),
        web_linked=bool(client.get("user_id")),
        silent_days=_silent_days(case),
        package_codes=[str(o.get("package_code")) for o in orders if o.get("package_code")],
        next_action=(work or {}).get("next_action")
        or derive_next_action(case, derive_waiting_on(case)),
        next_action_at=(work or {}).get("next_action_at") or case.get("next_action_at"),
        waiting_on=(work or {}).get("waiting_on") or derive_waiting_on(case),
        priority=(work or {}).get("priority"),
        deadline_status=(work or {}).get("deadline_status"),
        is_test=is_test_case(case),
        last_event=(work or {}).get("last_event"),
        finance_attention=derive_finance_attention(case),
        loss_reason=str(case.get("loss_reason") or "") or None,
        sales_board_column=_sales_column(case, work),
    )


def _sales_column(case: dict[str, Any], work: dict[str, Any] | None) -> str:
    from sfrfr.services.sales_board import sales_board_column

    waiting = (work or {}).get("waiting_on") or derive_waiting_on(case)
    return sales_board_column(
        pipeline_status=str(case.get("pipeline_status") or ""),
        b2c_status=str(case.get("b2c_status") or ""),
        waiting_on=str(waiting or ""),
        finance_attention=derive_finance_attention(case),
        loss_reason=str(case.get("loss_reason") or "") or None,
    )


def _staff_documents(
    raw_docs: list[Any] | None,
    *,
    can_view_ocr: bool,
) -> list[dict[str, Any]]:
    """Таблица документов как у клиента; OCR-превью — только эксперт/админ."""
    docs = _client_documents(raw_docs)
    if can_view_ocr:
        return docs
    for item in docs:
        item.pop("content_preview", None)
    return docs


def _filter_staff_case(
    case: dict[str, Any],
    principal: Principal,
    *,
    representatives: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Оператор не видит OCR/findings/черновик; эксперт и админ — полный контур."""
    client = case.get("clients") or {}
    settings = get_settings()
    base: dict[str, Any] = {
        "id": str(case["id"]),
        "pipeline_status": case.get("pipeline_status"),
        "b2c_status": case.get("b2c_status"),
        "created_at": case.get("created_at"),
        "first_contact_at": case.get("first_contact_at"),
        "expert_user_id": case.get("expert_user_id"),
        "crm_external_id": case.get("crm_external_id"),
        "crm_url": _crm_url(case.get("crm_external_id")),
        "meeting_url": case.get("meeting_url"),
        "tracker_last_issue_key": case.get("tracker_last_issue_key"),
        "tracker_issue_url": (
            f"https://tracker.yandex.ru/{case['tracker_last_issue_key']}"
            if case.get("tracker_last_issue_key")
            else None
        ),
        "next_action": case.get("next_action"),
        "next_action_at": case.get("next_action_at"),
        "waiting_on": case.get("waiting_on") or derive_waiting_on(case),
        "silent_days": _silent_days(case),
        "loss_reason": case.get("loss_reason"),
        "closed_at": case.get("closed_at"),
        "archive_prep_status": case.get("archive_prep_status"),
        "archive_tariff": case.get("archive_tariff"),
        "archive_successor": case.get("archive_successor"),
        "archive_target": case.get("archive_target"),
        "archive_followup_at": case.get("archive_followup_at"),
        "is_test": is_test_case(case),
        "segment": case.get("segment"),
        "region_bucket": case.get("region_bucket"),
        "problem_type": case.get("problem_type"),
        "client": {
            "full_name": client.get("full_name"),
            "phone": client.get("phone"),
            "email": client.get("email"),
            "preferred_channel": client.get("preferred_channel") or "unset",
            "preferred_channel_set_at": client.get("preferred_channel_set_at"),
            "max_linked": bool(client.get("max_user_id")),
            "web_linked": bool(client.get("user_id")),
            # max_user_id не отдаём оператору целиком — только флаг (ТЗ-09 конфликт → админ/эксп.)
            "max_user_id": (
                client.get("max_user_id")
                if principal.role in (StaffRole.ADMIN, StaffRole.EXPERT)
                else None
            ),
        },
        "documents": _staff_documents(
            list(case.get("documents") or []),
            can_view_ocr=principal.role in (StaffRole.ADMIN, StaffRole.EXPERT),
        ),
        "checklist_items": case.get("checklist_items") or [],
        "channels": {
            "cabinet_url": (
                f"{settings.cabinet_public_url.rstrip('/')}/cases/{case['id']}"
            ),
            "staff_cabinet_url": admin_case_max_reply_url(str(case["id"])),
            "max_reply_url": admin_case_max_reply_url(str(case["id"])),
            "max_business_url": max_business_dialogs_url(),
            "max_ops_bot_url": staff_max_login_url(),
        },
        "representatives": representatives if representatives is not None else [],
        "role_capabilities": {
            "can_edit_pipeline": principal.role in (StaffRole.EXPERT, StaffRole.ADMIN),
            "can_edit_checklist": principal.role in (StaffRole.EXPERT, StaffRole.ADMIN),
            "can_confirm_result": principal.role in (StaffRole.EXPERT, StaffRole.ADMIN),
            "can_manage_orders": principal.role in (StaffRole.EXPERT, StaffRole.ADMIN),
            "can_manage_roles": principal.role is StaffRole.ADMIN,
            "can_view_ocr": principal.role in (StaffRole.EXPERT, StaffRole.ADMIN),
            "can_knowledge_feedback": principal.role in (StaffRole.EXPERT, StaffRole.ADMIN),
        },
    }
    if principal.role in (StaffRole.EXPERT, StaffRole.ADMIN):
        pipeline = CaseRepository._one_or_none(
            get_supabase_client()
            .table("case_pipeline_data")
            .select("*")
            .eq("case_id", case["id"])
            .limit(1)
            .execute()
        )
        base["pipeline_data"] = pipeline
        base["ocr_texts"] = (pipeline or {}).get("ocr_texts") or []
        base["ils_periods"] = (pipeline or {}).get("ils_periods") or []
        base["labor_periods"] = (pipeline or {}).get("labor_periods") or []
        base["findings"] = (pipeline or {}).get("findings") or []
        base["analysis_notes"] = (pipeline or {}).get("analysis_notes")
        base["draft"] = (pipeline or {}).get("draft")
        base["classifications"] = (pipeline or {}).get("classifications") or []
    return base


def _load_ingest_document(case_id: str, document_id: str) -> dict[str, Any] | None:
    return CaseRepository._one_or_none(
        get_supabase_client()
        .table("documents")
        .select("*")
        .eq("id", document_id)
        .eq("case_id", case_id)
        .limit(1)
        .execute()
    )


def _queue_ingest_again(
    *,
    case_id: str,
    document_id: str,
    principal: Principal,
) -> str:
    client = get_supabase_client()
    existing = CaseRepository._one_or_none(
        client.table("document_ingest_jobs")
        .select("id")
        .eq("document_id", document_id)
        .eq("job_type", "ingest")
        .limit(1)
        .execute()
    )
    if existing:
        job_id = str(existing["id"])
        client.table("document_ingest_jobs").update(
            {
                "status": "queued",
                "attempts": 0,
                "progress_percent": 5,
                "current_stage": "security_check",
                "last_error": None,
                "available_at": datetime.now(UTC).isoformat(),
                "locked_by": None,
                "locked_at": None,
            }
        ).eq("id", job_id).execute()
    else:
        job_id = enqueue_document_ingest_job(case_id=case_id, document_id=document_id)
    client.table("documents").update(
        {
            "ingest_status": "security_check",
            "progress_percent": 5,
            "current_stage": "security_check",
            "progress_message": "Повторяем проверку документа.",
            "ingest_review_required": False,
        }
    ).eq("id", document_id).eq("case_id", case_id).execute()
    _repo().audit(case_id, principal.audit_actor_id(), "ingest_rerun")
    return job_id


@router.get("/admin/cases/{case_id}/ingest-review")
def list_ingest_review_documents(
    case_id: str,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Очередь документов, которым нужна проверка безопасности или OCR экспертом."""
    _repo().require_case(principal, case_id)
    rows = (
        get_supabase_client()
        .table("documents")
        .select("*")
        .eq("case_id", case_id)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    review_rows = [
        row
        for row in rows
        if bool(row.get("ingest_review_required"))
        or str(row.get("ingest_status") or "")
        in {"manual_review", "security_check"}
        or str(row.get("antivirus_status") or "") in {"pending", "error"}
    ]
    return {
        "case_id": case_id,
        "documents": _staff_documents(
            review_rows,
            can_view_ocr=principal.role in (StaffRole.EXPERT, StaffRole.ADMIN),
        ),
        "count": len(review_rows),
    }


@router.get("/admin/cases/{case_id}/documents/{document_id}/ingest-artifacts")
def get_ingest_artifacts(
    case_id: str,
    document_id: str,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Отдать экспертам extracted.md и ingest.json из private Storage."""
    _require_expert(principal)
    _repo().require_case(principal, case_id)
    row = _load_ingest_document(case_id, document_id)
    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    extracted_path = str(row.get("ingest_artifact_path") or "")
    manifest_path = str(row.get("ingest_manifest_path") or "")
    if not extracted_path or not manifest_path:
        raise HTTPException(status_code=404, detail="ingest artifacts not found")
    storage = get_supabase_client().storage.from_(PRIVATE_STORAGE_BUCKET)
    try:
        extracted = storage.download(extracted_path).decode("utf-8", errors="replace")
        manifest = json.loads(storage.download(manifest_path).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="ingest artifacts unavailable") from exc
    _repo().audit(case_id, principal.audit_actor_id(), "ingest_artifacts_viewed")
    return {"document_id": document_id, "extracted_text": extracted, "manifest": manifest}


@router.post("/admin/cases/{case_id}/documents/{document_id}/ingest-accept")
def accept_ingest_document(
    case_id: str,
    document_id: str,
    payload: dict[str, Any] = Body(...),
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Принять OCR после сверки оригинала и текста."""
    _require_expert(principal)
    _repo().require_case(principal, case_id)
    row = _load_ingest_document(case_id, document_id)
    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    if str(row.get("antivirus_status") or "") in {"pending", "error", "infected"}:
        raise HTTPException(status_code=409, detail="security check must be completed first")
    text = str(payload.get("extracted_text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="extracted_text required")
    fields: dict[str, Any] = {
        "ingest_review_required": False,
        "ingest_status": "ocr_done",
        "progress_percent": 100,
        "current_stage": "ocr_done",
        "progress_message": "Текст подтверждён экспертом.",
    }
    fields["content_preview"] = text[:2000]
    artifact_path = str(row.get("ingest_artifact_path") or "")
    manifest_path = str(row.get("ingest_manifest_path") or "")
    if artifact_path:
        try:
            storage = get_supabase_client().storage.from_(PRIVATE_STORAGE_BUCKET)
            storage.upload(
                artifact_path,
                text.encode("utf-8"),
                {"content-type": "text/markdown; charset=utf-8", "x-upsert": "true"},
            )
            if manifest_path:
                manifest = json.loads(storage.download(manifest_path).decode("utf-8"))
                if isinstance(manifest, dict):
                    manifest["needs_ingest_review"] = False
                    manifest["reviewed_at"] = datetime.now(UTC).isoformat()
                    storage.upload(
                        manifest_path,
                        json.dumps(manifest, ensure_ascii=False).encode("utf-8"),
                        {"content-type": "application/json", "x-upsert": "true"},
                    )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=502,
                detail="ingest artifact update failed",
            ) from exc
    client = get_supabase_client()
    client.table("documents").update(fields).eq(
        "id", document_id
    ).eq("case_id", case_id).execute()
    client.table("document_ingest_jobs").update(
        {
            "status": "completed",
            "progress_percent": 100,
            "current_stage": "ocr_done",
            "last_error": None,
            "locked_by": None,
            "locked_at": None,
        }
    ).eq("document_id", document_id).eq("job_type", "ingest").execute()
    if bool(payload.get("text_edited")):
        _repo().audit(case_id, principal.audit_actor_id(), "ingest_edit")
    _repo().audit(case_id, principal.audit_actor_id(), "ingest_accept")
    return {"ok": True, "document_id": document_id, "status": fields["ingest_status"]}


@router.post("/admin/cases/{case_id}/documents/{document_id}/ingest-reject")
def reject_ingest_document(
    case_id: str,
    document_id: str,
    payload: dict[str, Any] | None = Body(default=None),
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Вернуть документ клиенту на повторную загрузку."""
    _repo().require_case(principal, case_id)
    row = _load_ingest_document(case_id, document_id)
    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    reason = str((payload or {}).get("reason") or "").strip()[:300]
    message = reason or "Нужна более чёткая копия документа."
    client = get_supabase_client()
    client.table("documents").update(
        {
            "ingest_status": "needs_reupload",
            "progress_percent": 100,
            "current_stage": "needs_reupload",
            "progress_message": message,
            "ingest_review_required": False,
        }
    ).eq("id", document_id).eq("case_id", case_id).execute()
    client.table("checklist_items").insert(
        {
            "case_id": case_id,
            "title": "Повторно загрузить документ после проверки ingest",
            "item_type": "document",
                   "owner": "client",
                   "status": "open",
                   "sort_order": 50,
            "requirement_code": row.get("requirement_code") or "document_reupload",
            "reason_for_request": message,
            "requested_by": principal.audit_actor_id(),
            "requested_at": datetime.now(UTC).isoformat(),
        }
    ).execute()
    _repo().audit(case_id, principal.audit_actor_id(), "ingest_reject")
    return {"ok": True, "document_id": document_id, "status": "needs_reupload"}


@router.post("/admin/cases/{case_id}/documents/{document_id}/security-approve")
def approve_document_security(
    case_id: str,
    document_id: str,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Ручное подтверждение безопасности, если ClamAV недоступен."""
    _require_expert(principal)
    _repo().require_case(principal, case_id)
    client = get_supabase_client()
    row = _load_ingest_document(case_id, document_id)
    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    client.table("documents").update(
        {
            "antivirus_status": "clean",
            "security_reason": "manual_expert_approval",
            "security_checked_at": datetime.now(UTC).isoformat(),
        }
    ).eq("id", document_id).eq("case_id", case_id).execute()
    job_id = _queue_ingest_again(
        case_id=case_id,
        document_id=document_id,
        principal=principal,
    )
    _repo().audit(case_id, principal.audit_actor_id(), "security_manual_approve")
    return {"ok": True, "document_id": document_id, "job_id": job_id}


@router.post("/admin/cases/{case_id}/documents/{document_id}/ingest-rerun")
def rerun_ingest_document(
    case_id: str,
    document_id: str,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Поставить документ в очередь ingest повторно."""
    _require_expert(principal)
    _repo().require_case(principal, case_id)
    if not _load_ingest_document(case_id, document_id):
        raise HTTPException(status_code=404, detail="document not found")
    job_id = _queue_ingest_again(
        case_id=case_id,
        document_id=document_id,
        principal=principal,
    )
    return {"ok": True, "document_id": document_id, "job_id": job_id}


@router.get("/admin/dashboard", response_model=DashboardResponse)
def admin_dashboard(principal: Principal = Depends(require_staff)) -> DashboardResponse:
    cases = _repo().list_cases(principal)
    all_orders = _repo().list_all_orders()
    if principal.role is StaffRole.ADMIN:
        orders = all_orders
    else:
        case_ids = {str(c["id"]) for c in cases}
        orders = [o for o in all_orders if str(o.get("case_id")) in case_ids]

    snap = build_dashboard_snapshot(
        cases,
        orders,
        show_contact=principal.role in (StaffRole.OPERATOR, StaffRole.ADMIN, StaffRole.EXPERT),
    )

    channel_conflicts = 0
    unlinked_max = 0
    unlinked_web = 0
    for case in cases:
        client = case.get("clients") or {}
        max_linked = bool(client.get("max_user_id"))
        web_linked = bool(client.get("user_id"))
        if not max_linked:
            unlinked_max += 1
        if not web_linked:
            unlinked_web += 1
        preferred = client.get("preferred_channel") or "unset"
        if preferred == "max_miniapp" and not max_linked:
            channel_conflicts += 1
        if preferred == "web_cabinet" and not web_linked:
            channel_conflicts += 1

    return DashboardResponse(
        new_leads=snap["new_leads"],
        by_pipeline=snap["by_pipeline"],
        by_b2c=snap["by_b2c"],
        payments_pending=snap["payments_pending"],
        payments_paid=snap["payments_paid"],
        silent=snap["silent"],
        channel_conflicts=channel_conflicts,
        unlinked_max=unlinked_max,
        unlinked_web=unlinked_web,
        needs_reply=snap["needs_reply"],
        needs_reply_over_30m=snap["needs_reply_over_30m"],
        deadline_today=snap["deadline_today"],
        waiting_docs=snap["waiting_docs"],
        waiting_docs_max_days=snap["waiting_docs_max_days"],
        sla_risk=snap["sla_risk"],
        greeting_priority_count=snap["greeting_priority_count"],
        payments_pending_amount=snap["payments_pending_amount"],
        payments_paid_today=snap["payments_paid_today"],
        payments_paid_today_amount=snap["payments_paid_today_amount"],
        sla_control=snap["sla_control"],
        doc_status=snap["doc_status"],
        work_queue=[WorkQueueItem.model_validate(row) for row in snap["work_queue"]],
        my_tasks_today=[WorkQueueItem.model_validate(row) for row in snap["my_tasks_today"]],
    )


@router.get("/admin/cases", response_model=list[StaffCaseSummary])
def admin_list_cases(
    q: str | None = Query(default=None, max_length=120),
    pipeline_status: str | None = None,
    expert_user_id: str | None = None,
    package_code: str | None = None,
    payment_status: str | None = None,
    preferred_channel: str | None = None,
    queue: str | None = Query(default=None, max_length=32),
    include_test: bool = False,
    principal: Principal = Depends(require_staff),
) -> list[StaffCaseSummary]:
    cases = _repo().list_cases(principal)
    needle = (q or "").strip().lower()
    result: list[StaffCaseSummary] = []
    for case in cases:
        test = is_test_case(case)
        if queue == "test":
            if not test:
                continue
        elif not include_test and test:
            continue
        if pipeline_status and case.get("pipeline_status") != pipeline_status:
            continue
        if expert_user_id and str(case.get("expert_user_id") or "") != expert_user_id:
            continue
        client = case.get("clients") or {}
        if preferred_channel and (client.get("preferred_channel") or "unset") != preferred_channel:
            continue
        orders = case.get("orders") or []
        codes = {str(o.get("package_code")) for o in orders}
        if package_code and package_code not in codes:
            continue
        if payment_status and not any(o.get("status") == payment_status for o in orders):
            continue
        if needle:
            hay = " ".join(
                [
                    str(case.get("id") or ""),
                    str(client.get("full_name") or ""),
                    str(client.get("phone") or ""),
                    str(case.get("crm_external_id") or ""),
                ]
            ).lower()
            if needle not in hay:
                continue
        summary = _staff_summary(case, role=principal.role)
        if queue and queue != "test" and not _queue_match(summary, queue, principal):
            continue
        result.append(summary)
    return result


def _queue_match(item: StaffCaseSummary, queue: str, principal: Principal) -> bool:
    if queue in {"all", "active"}:
        return item.pipeline_status not in {"completed", "failed"} and item.b2c_status != "closed"
    if queue == "mine":
        return bool(item.expert_user_id and item.expert_user_id == principal.user_id)
    if queue == "new":
        return item.pipeline_status == "intake" or item.b2c_status == "lead"
    if queue == "reply":
        return item.waiting_on == "staff"
    if queue == "today":
        return item.priority == "today" or item.deadline_status == "today"
    if queue == "overdue":
        return item.deadline_status == "overdue"
    if queue == "docs":
        return item.waiting_on in {"client", "archive"}
    if queue == "payment":
        return item.waiting_on == "payment" or item.finance_attention in {
            "payable",
            "awaiting_invoice",
        }
    if queue == "noconsent":
        return item.b2c_status == "lead"
    if queue == "conflicts":
        pref = item.preferred_channel
        if pref == "max_miniapp" and not item.max_linked:
            return True
        if pref == "web_cabinet" and not item.web_linked:
            return True
        return False
    return True


@router.get("/admin/cases/{case_id}")
def admin_get_case(
    case_id: str,
    principal: Principal = Depends(require_staff),
) -> dict:
    repo = _repo()
    case = repo.require_case(principal, case_id)
    repo.audit(case_id, principal.user_id, "staff_case_viewed")
    payload = _filter_staff_case(
        case,
        principal,
        representatives=repo.list_representatives(case_id),
    )
    if principal.role is StaffRole.OPERATOR:
        payload["orders"] = []
        # оператор видит только факт наличия счетов, без сумм платежей
        payload["orders_summary"] = [
            {"package_code": o.get("package_code"), "status": o.get("status")}
            for o in repo.list_orders(case_id)
        ]
    else:
        from sfrfr.services.staff_finance import serialize_order

        order_rows = repo.list_orders(case_id)
        payload["orders"] = [serialize_order(o, case) for o in order_rows]
        payload["orders_summary"] = [
            {
                "package_code": o.get("package_code"),
                "status": o.get("status"),
                "finance_status": o.get("finance_status"),
                "amount_rub": o.get("amount_rub"),
            }
            for o in payload["orders"]
        ]
    payload["result"] = None
    if principal.role in (StaffRole.EXPERT, StaffRole.ADMIN):
        evidence = repo.get_result_evidence(case_id) or {}
        before = float(evidence.get("monthly_before_rub") or 0)
        after = float(evidence.get("monthly_after_rub") or 0)
        lump = float(evidence.get("lump_sum_rub") or 0)
        payload["result"] = {
            "evidence": evidence or None,
            "success_fee": calc_success_fee(
                lump_sum_rub=lump, monthly_increase_rub=max(after - before, 0)
            ),
        }
    payload["audit"] = repo.list_audit(case_id)
    payload["consent_accepted"] = repo.has_consent(case_id)
    try:
        from sfrfr.integrations.yandex_tracker.quality_issues import list_case_tracker_issues

        payload["tracker_issues"] = list_case_tracker_issues(case_id)
    except Exception:  # noqa: BLE001
        payload["tracker_issues"] = []
    return payload


@router.patch("/admin/cases/{case_id}/pipeline-status", response_model=CaseSummary)
def update_pipeline_status(
    case_id: str,
    payload: CaseStatusUpdate,
    principal: Principal = Depends(require_staff),
) -> CaseSummary:
    _require_expert(principal)
    repo = _repo()
    case = repo.require_case(principal, case_id)
    repo.update_case_status(case_id, payload.pipeline_status.value, principal.user_id)
    case["pipeline_status"] = payload.pipeline_status.value
    _push_case_crm(case, task=f"pipeline:{payload.pipeline_status.value}")
    checklist = case.get("checklist_items") or []
    return CaseSummary(
        id=str(case["id"]),
        pipeline_status=case["pipeline_status"],
        b2c_status=case["b2c_status"],
        created_at=case.get("created_at"),
        expert_user_id=str(case["expert_user_id"]) if case.get("expert_user_id") else None,
        expert_assigned=bool(case.get("expert_user_id")),
        checklist_open_count=sum(1 for item in checklist if item.get("status") != "done"),
        consent_accepted=repo.has_consent(case_id),
    )


@router.patch("/admin/cases/{case_id}/next-action")
def update_next_action(
    case_id: str,
    payload: CaseNextActionUpdate,
    principal: Principal = Depends(require_staff),
) -> dict:
    repo = _repo()
    repo.require_case(principal, case_id)
    updated = repo.update_next_action(
        case_id,
        principal.user_id,
        next_action=payload.next_action,
        next_action_at=payload.next_action_at,
        waiting_on=payload.waiting_on,
    )
    return {
        "id": str(updated.get("id") or case_id),
        "next_action": updated.get("next_action"),
        "next_action_at": updated.get("next_action_at"),
        "waiting_on": updated.get("waiting_on"),
    }


@router.post("/admin/cases/{case_id}/close")
def close_case(
    case_id: str,
    payload: CaseCloseRequest,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Закрыть дело успешно или с причиной отказа (LOSS в кабинете, не в amo)."""
    _require_expert(principal)
    repo = _repo()
    case = repo.require_case(principal, case_id)
    updated = repo.close_case(
        case_id,
        principal.user_id,
        outcome=payload.outcome,
        loss_reason=payload.loss_reason,
    )
    case = {**case, **updated}
    # amo reserved: push best-effort only if AMOCRM_ENABLED
    _push_case_crm(case, task=f"close:{payload.outcome}")
    return {
        "id": case_id,
        "b2c_status": updated.get("b2c_status"),
        "loss_reason": updated.get("loss_reason"),
        "closed_at": updated.get("closed_at"),
        "next_action": updated.get("next_action"),
    }


@router.patch("/admin/cases/{case_id}/archive-prep")
def update_archive_prep(
    case_id: str,
    payload: CaseArchivePrepUpdate,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Операционные поля подготовки архивного комплекта (без ПДн)."""
    repo = _repo()
    repo.require_case(principal, case_id)
    updated = repo.update_archive_prep(
        case_id,
        principal.user_id,
        archive_prep_status=payload.archive_prep_status,
        archive_tariff=payload.archive_tariff,
        archive_successor=payload.archive_successor,
        archive_target=payload.archive_target,
        archive_followup_at=payload.archive_followup_at,
    )
    return {
        "id": str(updated.get("id") or case_id),
        "archive_prep_status": updated.get("archive_prep_status"),
        "archive_tariff": updated.get("archive_tariff"),
        "archive_successor": updated.get("archive_successor"),
        "archive_target": updated.get("archive_target"),
        "archive_followup_at": updated.get("archive_followup_at"),
    }


@router.post("/admin/cases/{case_id}/suggest-next-action")
def suggest_case_next_action(
    case_id: str,
    principal: Principal = Depends(require_staff),
) -> dict:
    """DeepSeek (Yandex AI Studio) предлагает следующий шаг без ПДн."""
    repo = _repo()
    case = repo.require_case(principal, case_id)
    return suggest_next_action(case)


@router.post("/admin/cases/{case_id}/suggest-replies")
def suggest_case_replies(
    case_id: str,
    principal: Principal = Depends(require_staff),
) -> dict:
    """DeepSeek: 2–3 варианта ответа клиенту в MAX (с обращением по имени)."""
    repo = _repo()
    case = repo.require_case(principal, case_id)
    messages = (
        get_supabase_client()
        .table("case_messages")
        .select("author_kind, body, created_at")
        .eq("case_id", case_id)
        .order("created_at")
        .limit(40)
        .execute()
        .data
        or []
    )
    client = case.get("clients") if isinstance(case.get("clients"), dict) else {}
    client_name = ""
    if isinstance(client, dict):
        client_name = str(client.get("full_name") or "").strip()
    work: dict[str, Any] = {}
    try:
        from sfrfr.services.case_chat_context import work_map_from_case

        work = work_map_from_case(case)
    except Exception:  # noqa: BLE001
        work = {}
    suggestions = suggest_staff_replies(
        messages=messages,
        pipeline_status=str(case.get("pipeline_status") or ""),
        b2c_status=str(case.get("b2c_status") or ""),
        client_name=client_name or None,
        work=work or None,
    )
    return {"suggestions": suggestions, "source": "deepseek"}


@router.patch("/admin/cases/{case_id}/flags")
def update_case_flags(
    case_id: str,
    payload: CaseFlagsUpdate,
    principal: Principal = Depends(require_staff),
) -> dict:
    if principal.role is not StaffRole.ADMIN:
        raise HTTPException(status_code=403, detail="admin role required")
    repo = _repo()
    repo.require_case(principal, case_id)
    updated = repo.update_case_flags(case_id, principal.user_id, is_test=payload.is_test)
    return {"id": str(updated.get("id") or case_id), "is_test": bool(updated.get("is_test"))}


@router.patch("/admin/cases/{case_id}/assign-expert")
def assign_expert(
    case_id: str,
    payload: AssignExpertRequest,
    principal: Principal = Depends(require_staff),
) -> dict:
    if principal.role is StaffRole.EXPERT:
        if payload.expert_user_id != principal.user_id:
            raise HTTPException(status_code=403, detail="expert can only take own case")
    elif principal.role not in (StaffRole.OPERATOR, StaffRole.ADMIN):
        raise HTTPException(status_code=403, detail="operator or admin role required")
    repo = _repo()
    repo.require_case(principal, case_id)
    return repo.assign_expert(case_id, payload.expert_user_id, principal.user_id)


@router.get("/admin/cases/{case_id}/representatives")
def list_case_representatives(
    case_id: str,
    principal: Principal = Depends(require_staff),
) -> dict:
    """Законные представители дела (ТЗ-03)."""
    repo = _repo()
    repo.require_case(principal, case_id)
    return {"items": repo.list_representatives(case_id)}


@router.post("/admin/cases/{case_id}/representatives", status_code=201)
def add_case_representative(
    case_id: str,
    payload: dict[str, Any],
    principal: Principal = Depends(require_staff),
) -> dict:
    """Выдать доступ представителю по email или user_id (staff)."""
    if principal.role not in (StaffRole.OPERATOR, StaffRole.ADMIN, StaffRole.EXPERT):
        raise HTTPException(status_code=403, detail="staff role required")
    repo = _repo()
    repo.require_case(principal, case_id)
    email = (payload.get("email") or "").strip() or None
    user_id = (payload.get("user_id") or "").strip() or None
    return repo.add_representative(
        case_id, actor_id=principal.user_id, user_id=user_id, email=email
    )


@router.delete("/admin/cases/{case_id}/representatives/{user_id}")
def remove_case_representative(
    case_id: str,
    user_id: str,
    principal: Principal = Depends(require_staff),
) -> dict:
    if principal.role not in (StaffRole.OPERATOR, StaffRole.ADMIN, StaffRole.EXPERT):
        raise HTTPException(status_code=403, detail="staff role required")
    repo = _repo()
    repo.require_case(principal, case_id)
    return repo.remove_representative(case_id, user_id=user_id, actor_id=principal.user_id)


@router.post("/admin/cases/{case_id}/checklist", status_code=201)
def create_checklist_item(
    case_id: str,
    payload: ChecklistItemCreate,
    principal: Principal = Depends(require_staff),
) -> dict:
    _require_expert(principal)
    repo = _repo()
    repo.require_case(principal, case_id)
    return repo.upsert_checklist_item(
        case_id,
        title=payload.title,
        item_type=payload.item_type,
        owner=payload.owner,
        actor_id=principal.user_id,
        due_at=payload.due_at,
        note=payload.note,
        sort_order=payload.sort_order,
    )


@router.post("/admin/cases/{case_id}/document-requirements", status_code=201)
def create_document_requirement(
    case_id: str,
    payload: dict[str, Any],
    principal: Principal = Depends(require_staff),
) -> dict:
    """Staff-only запрос дополнительного документа (в т.ч. банковская выписка)."""
    from sfrfr.services.document_requirements import (
        BANK_REQUIREMENT_CODE,
        BANK_STAFF_TITLE,
        SCENARIO_BANK_LIMITED,
    )

    _require_expert(principal)
    repo = _repo()
    repo.require_case(principal, case_id)
    requirement_code = str(payload.get("requirement_code") or "").strip()
    reason = str(payload.get("reason_for_request") or "").strip()
    if not requirement_code:
        raise HTTPException(status_code=400, detail="requirement_code required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason_for_request required")
    title = str(payload.get("title") or "").strip()
    if requirement_code == BANK_REQUIREMENT_CODE:
        title = title or BANK_STAFF_TITLE
        repo.set_case_scenarios(
            case_id, {SCENARIO_BANK_LIMITED}, source="staff", actor_id=principal.user_id
        )
    if not title:
        title = requirement_code
    return repo.create_document_requirement(
        case_id,
        title=title,
        requirement_code=requirement_code,
        category=str(payload.get("category") or "staff_requested"),
        actor_id=principal.user_id,
        reason_for_request=reason,
        scenario_code=payload.get("scenario_code"),
        consent_required=bool(
            payload.get("consent_required", requirement_code == BANK_REQUIREMENT_CODE)
        ),
        period_from=payload.get("period_from"),
        period_to=payload.get("period_to"),
    )


@router.patch("/admin/cases/{case_id}/checklist/{item_id}")
def update_checklist_item(
    case_id: str,
    item_id: str,
    payload: ChecklistItemUpdate,
    principal: Principal = Depends(require_staff),
) -> dict:
    _require_expert(principal)
    repo = _repo()
    repo.require_case(principal, case_id)
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="empty update")
    return repo.update_checklist_item(
        case_id, item_id, actor_id=principal.user_id, updates=updates
    )


@router.post("/admin/cases/{case_id}/request-review")
def request_review(
    case_id: str,
    principal: Principal = Depends(require_staff),
) -> dict:
    """Оператор/эксперт: запросить проверку (единая семантика с client run, ТЗ-09)."""
    repo = _repo()
    repo.require_case(principal, case_id)
    return repo.request_pipeline_run(case_id, principal.user_id)


@router.post("/admin/cases/{case_id}/max-reply")
def send_max_reply_to_client(
    case_id: str,
    payload: MaxReplyRequest,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Отправить сообщение клиенту в его личный чат с клиентским ботом MAX."""
    if principal.role not in (StaffRole.OPERATOR, StaffRole.ADMIN, StaffRole.EXPERT):
        raise HTTPException(status_code=403, detail="forbidden")
    from sfrfr.services.message_dedupe import (
        count_same_messages,
        find_duplicate_staff_message,
    )

    repo = _repo()
    case = repo.require_case(principal, case_id)
    client = case.get("clients") or {}
    max_uid = str(client.get("max_user_id") or "").strip()
    if not max_uid:
        raise HTTPException(status_code=400, detail="client_has_no_max_user_id")
    text = strip_internal_staff_prefix(payload.message.strip())
    if not text:
        raise HTTPException(status_code=400, detail="empty_message")

    from sfrfr.db.marketing_consent_repository import MarketingConsentRepository
    from sfrfr.integrations.max.marketing_consent_flow import append_unsub_footer
    from sfrfr.services.marketing_consent import classify_template, gate_outbound_message

    kind = classify_template(payload.template_code, kind=payload.message_kind)
    try:
        mkt_rows = MarketingConsentRepository().list_for_contact(
            max_user_id=max_uid,
            email=str(client.get("email") or "") or None,
            client_id=str(client.get("id") or "") or None,
        )
        gate = gate_outbound_message(
            mkt_rows,
            channel="max",
            template_code=payload.template_code,
            message_kind=payload.message_kind,
        )
    except Exception as exc:  # noqa: BLE001 — таблица ещё не накатана
        if kind == "marketing":
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "marketing_consent_store_unavailable",
                    "detail": f"Журнал согласий недоступен: {type(exc).__name__}",
                },
            ) from exc
        gate = None
    if gate is not None and not gate.allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "code": gate.reason,
                "detail": (
                    "Нельзя отправить: согласие на рекламные сообщения в MAX не получено "
                    "или сообщение помечено как mixed. Сервисные сообщения по делу — "
                    "без marketing_*; шаблоны promo_/marketing_ требуют согласие."
                ),
                "channel": gate.channel,
                "consent_status": gate.status,
            },
        )
    if kind == "marketing":
        text = append_unsub_footer(text)

    sb = get_supabase_client()
    recent = (
        sb.table("case_messages")
        .select("id, author_kind, body, created_at")
        .eq("case_id", case_id)
        .in_("author_kind", ["staff", "system"])
        .order("created_at", desc=True)
        .limit(80)
        .execute()
        .data
        or []
    )
    same_48h = count_same_messages(
        recent,
        body=text,
        template_code=payload.template_code,
        within_hours=48.0,
    )
    if not payload.force:
        if same_48h >= 3:
            last = find_duplicate_staff_message(
                recent, body=text, template_code=payload.template_code, within_hours=48.0
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "duplicate_message_limit",
                    "detail": "Одинаковое сообщение уже отправлялось 3 раза за 48 часов.",
                    "last_at": (last or {}).get("created_at"),
                    "last_body_preview": str((last or {}).get("body") or "")[:160],
                    "count_48h": same_48h,
                },
            )
        dup = find_duplicate_staff_message(
            recent, body=text, template_code=payload.template_code, within_hours=24.0
        )
        if dup:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "duplicate_message",
                    "detail": "Этот запрос уже отправлялся за последние 24 часа.",
                    "last_at": dup.get("created_at"),
                    "last_body_preview": str(dup.get("body") or "")[:160],
                    "message_id": dup.get("id"),
                    "count_48h": same_48h,
                },
            )

    try:
        from sfrfr.db.case_messages_write import insert_case_message

        message_row = insert_case_message(
            {
                "case_id": case_id,
                "author_user_id": principal.user_id,
                "author_kind": "staff",
                "body": text,
                "channel_origin": "admin",
            }
        )
        message_id = str(message_row.get("id") or "").strip() or None
        from sfrfr.services.case_chat_delivery import mirror_staff_message_to_max

        mirror_staff_message_to_max(case, text, message_id=message_id)
    except Exception as exc:  # noqa: BLE001
        detail = (
            "Не удалось сохранить сообщение общего чата. "
            "Проверьте связь с базой и повторите."
        )
        raise HTTPException(status_code=502, detail=detail) from exc
    repo.audit(case_id, principal.audit_actor_id(), "staff_max_reply_sent")
    return {
        "ok": True,
        "max_user_id": max_uid,
        "message_id": message_id,
        "queued": True,
    }


@router.post("/admin/cases/{case_id}/telemost")
def create_case_telemost(
    case_id: str,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Создать встречу Яндекс Телемост и сохранить meeting_url (ТЗ-14)."""
    from sfrfr.db.session import get_supabase_client
    from sfrfr.integrations.yandex_workspace import create_conference

    repo = _repo()
    repo.require_case(principal, case_id)
    result = create_conference(title_note=f"case:{case_id}")
    if result.get("ok") and result.get("join_url"):
        try:
            get_supabase_client().table("cases").update(
                {"meeting_url": str(result["join_url"])}
            ).eq("id", case_id).execute()
            repo.audit(
                case_id,
                principal.audit_actor_id(),
                f"yandex_telemost_create:{result.get('conference_id')}",
            )
        except Exception as exc:  # noqa: BLE001
            result["persist_error"] = type(exc).__name__
            result["persist_detail"] = str(exc)[:200]
    return result


@router.get("/admin/tracker/health")
def tracker_integration_health(
    principal: Principal = Depends(require_admin),
) -> dict[str, Any]:
    """Health-check интеграции Трекер (только admin). Без токенов в ответе."""
    from sfrfr.integrations.yandex_tracker import health_check

    return health_check()


@router.get("/admin/cases/{case_id}/tracker-issues")
def list_case_tracker_issues_endpoint(
    case_id: str,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    from sfrfr.integrations.yandex_tracker.quality_issues import list_case_tracker_issues

    repo = _repo()
    repo.require_case(principal, case_id)
    return {"items": list_case_tracker_issues(case_id)}


@router.post("/admin/cases/{case_id}/tracker")
def create_case_tracker_issue(
    case_id: str,
    payload: TrackerQualityIssueRequest,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Создать обезличенную задачу в очереди STAZH (качество / продукт)."""
    from sfrfr.integrations.yandex_tracker.quality_issues import create_quality_issue_from_case

    repo = _repo()
    case = repo.require_case(principal, case_id)
    funnel = payload.funnel_stage or str(case.get("pipeline_status") or "")
    channel = payload.channel
    if channel is None:
        client = case.get("clients") or {}
        pref = str(client.get("preferred_channel") or "unset")
        channel = "max" if pref == "max" else ("web" if pref == "web" else "unknown")

    result = create_quality_issue_from_case(
        case_id=case_id,
        actor_id=principal.user_id,
        issue_type=payload.issue_type,
        priority=payload.priority,
        direction=payload.direction,
        source=payload.source,
        description=payload.description,
        component=payload.component,
        funnel_stage=funnel or None,
        channel=channel,
        age_bucket=payload.age_bucket,
        repeatability=payload.repeatability,
        correlation_id=payload.correlation_id,
        title_hint=payload.title_hint,
        force_new=payload.force_new,
    )
    key = result.get("tracker_issue_key")
    if key and result.get("ok") and not result.get("duplicate"):
        try:
            get_supabase_client().table("cases").update(
                {"tracker_last_issue_key": str(key)}
            ).eq("id", case_id).execute()
        except Exception:  # noqa: BLE001
            pass
        repo.audit(
            case_id,
            principal.audit_actor_id(),
            f"yandex_tracker_create:{key}:{payload.issue_type}",
        )
    elif result.get("duplicate") and key:
        repo.audit(
            case_id,
            principal.audit_actor_id(),
            f"yandex_tracker_duplicate:{key}:{payload.issue_type}",
        )
    return result


@router.post("/admin/cases/{case_id}/email")
def send_case_email(
    case_id: str,
    payload: YandexMailRequest,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Исходящее письмо с ящика Workspace (без вложений/OCR)."""
    from sfrfr.integrations.yandex_workspace import send_mail

    repo = _repo()
    case = repo.require_case(principal, case_id)
    client = case.get("clients") or {}
    if isinstance(client, list):
        client = client[0] if client else {}
    to_addr = (payload.to or client.get("email") or "").strip()
    if not to_addr:
        raise HTTPException(status_code=400, detail="client email required (or pass to)")
    result = send_mail(
        to=to_addr,
        template=payload.template,
        case_id=case_id,
        subject=payload.subject,
        body=payload.body,
    )
    if result.get("ok"):
        repo.audit(case_id, principal.audit_actor_id(), f"yandex_mail_send:{payload.template}")
    return result


@router.post("/admin/cases/{case_id}/diagnosis/publish")
def publish_diagnosis_result(
    case_id: str,
    payload: DiagnosisPublishRequest,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Триггер 1: publish → draft result_ready + задача сотруднику (ТЗ-28/30)."""
    from sfrfr.services.diagnosis_delivery import STAFF_TASK_PUBLISH, DiagnosisDeliveryService
    from sfrfr.services.finance_automation import ensure_staff_task

    repo = _repo()
    case = repo.require_case(principal, case_id)
    doc = CaseRepository._one_or_none(
        get_supabase_client()
        .table("documents")
        .select("id, doc_type")
        .eq("id", payload.document_id)
        .eq("case_id", case_id)
        .limit(1)
        .execute()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    try:
        out = DiagnosisDeliveryService().publish(
            case_id=case_id,
            document_id=payload.document_id,
            actor_id=principal.user_id,
            channels=list(payload.channels),
            checksum=payload.checksum,
            do_not_contact=bool(case.get("do_not_contact")),
            case_archived=str(case.get("status") or "") == "archived",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    repo.audit(case_id, principal.audit_actor_id(), "diagnostic_result_published")
    try:
        ensure_staff_task(
            repo,
            case_id,
            title=STAFF_TASK_PUBLISH,
            item_type="task",
            due_at=None,
            actor_id=principal.user_id,
            note="Черновик уведомления result_ready — проверить и отправить",
        )
        repo.update_next_action(
            case_id,
            principal.user_id,
            next_action=STAFF_TASK_PUBLISH,
            waiting_on="staff",
        )
    except Exception:  # noqa: BLE001
        pass
    return out


@router.get("/admin/cases/{case_id}/notification-jobs")
def list_notification_jobs(
    case_id: str,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    from sfrfr.db.diagnosis_delivery_repository import DiagnosisDeliveryRepository

    _repo().require_case(principal, case_id)
    jobs = DiagnosisDeliveryRepository().list_jobs(case_id)
    return {"jobs": jobs}


@router.post("/admin/cases/{case_id}/notification-jobs/{job_id}/approve")
def approve_notification_job(
    case_id: str,
    job_id: str,
    payload: NotificationJobApproveRequest,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Подтвердить отправку draft: email — SMTP; max — текст для чата."""
    from sfrfr.db.diagnosis_delivery_repository import DiagnosisDeliveryRepository
    from sfrfr.services.diagnosis_delivery import DiagnosisDeliveryService

    repo = _repo()
    case = repo.require_case(principal, case_id)
    job = DiagnosisDeliveryRepository().get_job(job_id)
    if not job or str(job.get("case_id")) != case_id:
        raise HTTPException(status_code=404, detail="job not found")

    client = case.get("clients") or {}
    if isinstance(client, list):
        client = client[0] if client else {}
    do_not = bool(case.get("do_not_contact"))  # если поля нет — False
    svc = DiagnosisDeliveryService()
    try:
        if job.get("channel") == "email":
            to_addr = (payload.to or client.get("email") or "").strip()
            if not to_addr:
                raise HTTPException(status_code=400, detail="client email required")
            out = svc.approve_and_send_email(
                job_id=job_id,
                actor_id=principal.user_id,
                to_email=to_addr,
                do_not_contact=do_not,
            )
        else:
            out = svc.approve_max_draft(
                job_id=job_id,
                actor_id=principal.user_id,
                do_not_contact=do_not,
            )
            if payload.mark_max_sent and out.get("ok"):
                svc.mark_max_sent(job_id)
                out["marked_sent"] = True
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    repo.audit(case_id, principal.audit_actor_id(), f"notification_job_approve:{job_id}")
    return out


@router.get("/admin/notification-jobs/failed")
def list_failed_notification_jobs(
    limit: int = 50,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Дашборд failed jobs (без ПДн в теле)."""
    from sfrfr.db.diagnosis_delivery_repository import DiagnosisDeliveryRepository

    _ = principal
    jobs = DiagnosisDeliveryRepository().list_failed_jobs(limit=limit)
    return {"jobs": jobs}


@router.post("/admin/notification-jobs/smtp-retry")
def run_smtp_retry_tick(
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """P1: backoff-retry failed email через Yandex SMTP (без авто-ESP API)."""
    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.db.diagnosis_delivery_repository import DiagnosisDeliveryRepository
    from sfrfr.services.diagnosis_delivery import DiagnosisDeliveryService

    _ = principal
    failed = DiagnosisDeliveryRepository().list_failed_jobs(limit=30)
    email_by_case: dict[str, str] = {}
    cases = CaseRepository()
    for job in failed:
        cid = str(job.get("case_id") or "")
        if not cid or cid in email_by_case:
            continue
        case = cases.get_case_row(cid)
        client = (case or {}).get("clients") or {}
        if isinstance(client, list):
            client = client[0] if client else {}
        # get_case_row may not embed clients — fetch email via client_id
        email = str(client.get("email") or "").strip()
        if not email and case and case.get("client_id"):
            try:
                crow = (
                    cases.client.table("clients")
                    .select("email")
                    .eq("id", case["client_id"])
                    .limit(1)
                    .execute()
                )
                rows = crow.data or []
                email = str((rows[0] if rows else {}).get("email") or "").strip()
            except Exception:  # noqa: BLE001
                email = ""
        if email:
            email_by_case[cid] = email
    stats = DiagnosisDeliveryService().retry_smtp_failures(email_by_case=email_by_case)
    return {"ok": True, **stats}


@router.get("/admin/email-delivery/dashboard")
def email_delivery_dashboard(
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Агрегаты webhook-доставки: delivered/bounce/complaint/unmatched (без ПДн)."""
    from sfrfr.db.email_delivery_repository import EmailDeliveryRepository

    _ = principal
    repo = EmailDeliveryRepository()
    return {
        "counts": repo.dashboard_counts(),
        "unmatched": repo.list_unmatched(limit=30),
        "note": "email delivered ≠ PDF opened; open/click — только аналитика",
    }


@router.post("/admin/diagnosis-delivery/unread-tick")
def run_unread_reminder_tick(
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Scheduler-тик: создать draft result_unread (макс. 1), без автоотправки."""
    from sfrfr.services.diagnosis_delivery import DiagnosisDeliveryService

    _ = principal
    stats = DiagnosisDeliveryService().run_unread_tick()
    return {"ok": True, **stats}


@router.post("/admin/diagnosis-surveys/due-tick")
def run_survey_due_tick(
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Scheduler: scheduled surveys → draft на Approve (без автоотправки)."""
    from sfrfr.services.diagnosis_survey import DiagnosisSurveyService

    _ = principal
    stats = DiagnosisSurveyService().run_due_tick()
    return {"ok": True, **stats}


@router.post("/admin/cases/{case_id}/notification-jobs/{job_id}/cancel")
def cancel_notification_job(
    case_id: str,
    job_id: str,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    from sfrfr.db.diagnosis_delivery_repository import DiagnosisDeliveryRepository
    from sfrfr.services.diagnosis_delivery import DiagnosisDeliveryService

    _repo().require_case(principal, case_id)
    job = DiagnosisDeliveryRepository().get_job(job_id)
    if not job or str(job.get("case_id")) != case_id:
        raise HTTPException(status_code=404, detail="job not found")
    out = DiagnosisDeliveryService().cancel_job(job_id)
    _repo().audit(case_id, principal.audit_actor_id(), f"notification_job_cancel:{job_id}")
    return out


@router.get("/admin/cases/{case_id}/diagnosis-feedback")
def get_diagnosis_feedback(
    case_id: str,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Статус обратной связи после PDF (ТЗ-27), без ПДн."""
    from sfrfr.db.diagnosis_feedback_repository import DiagnosisFeedbackRepository

    _repo().require_case(principal, case_id)
    row = DiagnosisFeedbackRepository().get(case_id)
    if not row:
        return {"feedback": None}
    safe = {
        k: row.get(k)
        for k in (
            "case_id",
            "pdf_issued_at",
            "pdf_opened_at",
            "feedback_status",
            "clarity_score",
            "expectation_match",
            "useful_section",
            "first_plan_step_status",
            "difficulty_category",
            "follow_up_service_requested",
            "review_publication_consent",
            "touch2_due_at",
            "touch3_due_at",
            "touch2_sent_at",
            "touch3_sent_at",
            "updated_at",
        )
    }
    return {"feedback": safe}


@router.get("/admin/cases/{case_id}/survey-campaigns")
def list_survey_campaigns(
    case_id: str,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Черновики и статусы сервисных опросов (ТЗ-29)."""
    from sfrfr.db.diagnosis_survey_repository import DiagnosisSurveyRepository

    _repo().require_case(principal, case_id)
    rows = DiagnosisSurveyRepository().list_campaigns(case_id)
    # Не отдавать токены; только метаданные.
    safe = [
        {
            "id": r.get("id"),
            "survey_type": r.get("survey_type"),
            "channel": r.get("channel"),
            "status": r.get("status"),
            "scheduled_at": r.get("scheduled_at"),
            "sent_at": r.get("sent_at"),
            "completed_at": r.get("completed_at"),
            "template_version": r.get("template_version"),
            "touch_index": r.get("touch_index"),
            "body": r.get("body"),
        }
        for r in rows
    ]
    return {"campaigns": safe}


@router.post("/admin/cases/{case_id}/survey-campaigns/{campaign_id}/approve")
def approve_survey_campaign(
    case_id: str,
    campaign_id: str,
    payload: SurveyCampaignApproveRequest,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Подтвердить MAX-опрос: вернуть body + tokens для кнопок (один раз)."""
    from sfrfr.db.diagnosis_survey_repository import DiagnosisSurveyRepository
    from sfrfr.integrations.max.survey_flow import survey_keyboard
    from sfrfr.services.diagnosis_survey import DiagnosisSurveyService

    repo = _repo()
    case = repo.require_case(principal, case_id)
    camp = DiagnosisSurveyRepository().get_campaign(campaign_id)
    if not camp or str(camp.get("case_id")) != case_id:
        raise HTTPException(status_code=404, detail="campaign not found")
    do_not = bool(payload.do_not_contact) or bool(case.get("do_not_contact"))
    try:
        out = DiagnosisSurveyService().approve_and_mark_sent(
            campaign_id=campaign_id,
            actor_id=principal.user_id,
            do_not_contact=do_not,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if out.get("ok") and out.get("tokens"):
        labels = out.get("labels") or {}
        tokens = out["tokens"]
        out["attachments"] = survey_keyboard(tokens, labels)
        channel = str(camp.get("channel") or "max")
        if channel == "email":
            from sfrfr.services.diagnosis_survey import survey_email_link

            out["email_links"] = [
                {
                    "answer_code": code,
                    "label": labels.get(code, code),
                    "url": survey_email_link(raw),
                }
                for code, raw in tokens.items()
            ]
        out.pop("tokens", None)
        if not payload.mark_sent:
            DiagnosisSurveyRepository().update_campaign(
                campaign_id,
                {"status": "approved", "updated_at": datetime.now(UTC).isoformat()},
            )
            out["status"] = "approved"
    repo.audit(case_id, principal.audit_actor_id(), f"survey_campaign_approve:{campaign_id}")
    return out


@router.post("/admin/cases/{case_id}/survey-campaigns/{campaign_id}/reschedule")
def reschedule_survey_campaign(
    case_id: str,
    campaign_id: str,
    payload: SurveyCampaignRescheduleRequest,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    from sfrfr.db.diagnosis_survey_repository import DiagnosisSurveyRepository

    _repo().require_case(principal, case_id)
    camp = DiagnosisSurveyRepository().get_campaign(campaign_id)
    if not camp or str(camp.get("case_id")) != case_id:
        raise HTTPException(status_code=404, detail="campaign not found")
    if camp.get("status") not in ("draft", "scheduled", "approved"):
        raise HTTPException(status_code=400, detail="cannot reschedule")
    DiagnosisSurveyRepository().update_campaign(
        campaign_id,
        {
            "scheduled_at": payload.scheduled_at,
            "status": "draft",
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )
    _repo().audit(case_id, principal.audit_actor_id(), f"survey_campaign_reschedule:{campaign_id}")
    return {"ok": True, "campaign_id": campaign_id, "scheduled_at": payload.scheduled_at}


@router.post("/admin/cases/{case_id}/survey-campaigns/{campaign_id}/cancel")
def cancel_survey_campaign(
    case_id: str,
    campaign_id: str,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    from sfrfr.db.diagnosis_survey_repository import DiagnosisSurveyRepository

    _repo().require_case(principal, case_id)
    camp = DiagnosisSurveyRepository().get_campaign(campaign_id)
    if not camp or str(camp.get("case_id")) != case_id:
        raise HTTPException(status_code=404, detail="campaign not found")
    DiagnosisSurveyRepository().update_campaign(
        campaign_id,
        {"status": "cancelled", "updated_at": datetime.now(UTC).isoformat()},
    )
    _repo().audit(case_id, principal.audit_actor_id(), f"survey_campaign_cancel:{campaign_id}")
    return {"ok": True, "campaign_id": campaign_id}


@router.get("/admin/mail/inbox")
def mail_inbox(
    limit: int = 20,
    unseen: bool = False,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Входящие на proverkastaza@yandex.ru — только метаданные."""
    from sfrfr.integrations.yandex_workspace import list_inbox

    _ = principal
    result = list_inbox(limit=min(max(limit, 1), 100), unseen_only=unseen)
    return result


@router.get("/admin/mail/messages/{uid}")
def mail_message(
    uid: str,
    body: bool = False,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Одно письмо по IMAP UID. Тело — только ?body=true, с маскированием ПДн."""
    from sfrfr.integrations.yandex_workspace import fetch_message

    _ = principal
    return fetch_message(uid, include_body=body, redact_body=True)


@router.post("/admin/cases/{case_id}/result/confirm")
def confirm_result(
    case_id: str,
    payload: ResultConfirmRequest,
    principal: Principal = Depends(require_staff),
) -> dict:
    _require_expert(principal)
    repo = _repo()
    repo.require_case(principal, case_id)
    evidence = repo.confirm_result(
        case_id,
        actor_id=principal.user_id,
        monthly_before_rub=payload.monthly_before_rub,
        monthly_after_rub=payload.monthly_after_rub,
        lump_sum_rub=payload.lump_sum_rub,
        result_effective_at=payload.result_effective_at,
    )
    case = repo.require_case(principal, case_id)
    case["b2c_status"] = "result_confirmed"
    _push_case_crm(case, task="result_confirmed")
    fee = calc_success_fee(
        lump_sum_rub=payload.lump_sum_rub,
        monthly_increase_rub=max(payload.monthly_after_rub - payload.monthly_before_rub, 0),
    )
    return {"evidence": evidence, "success_fee": fee}


@router.post("/admin/cases/{case_id}/orders", status_code=201)
def create_order(
    case_id: str,
    payload: OrderCreateRequest,
    principal: Principal = Depends(require_staff),
) -> dict:
    from sfrfr.services.message_dedupe import has_service_consent

    _require_expert(principal)
    if payload.package_code in ("SF_LUMP", "SF_MONTH") and principal.role is not StaffRole.ADMIN:
        raise HTTPException(status_code=403, detail="admin role required for success-fee orders")
    repo = _repo()
    case = repo.require_case(principal, case_id)
    audit_rows = (
        get_supabase_client()
        .table("access_audit")
        .select("action, at")
        .eq("case_id", case_id)
        .eq("action", "service_consent_recorded")
        .limit(1)
        .execute()
        .data
        or []
    )
    if not has_service_consent(case, audit_rows):
        raise HTTPException(
            status_code=400,
            detail="Сначала зафиксируйте согласие клиента на услугу",
        )
    if payload.package_code in ("SF_LUMP", "SF_MONTH"):
        evidence = repo.get_result_evidence(case_id)
        if not evidence or not evidence.get("confirmed_at"):
            raise HTTPException(status_code=400, detail="result must be confirmed first")
        confirmed = _parse_dt(str(evidence.get("confirmed_at")))
        effective = _parse_dt(str(evidence.get("result_effective_at") or "")) or confirmed
        if effective is None:
            raise HTTPException(status_code=400, detail="result_effective_at required")
        if effective.tzinfo is None:
            effective = effective.replace(tzinfo=UTC)
        earliest = effective + timedelta(days=SUCCESS_FEE_DELAY_DAYS_MIN)
        if datetime.now(UTC) < earliest:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"post-payment available after {SUCCESS_FEE_DELAY_DAYS_MIN} days "
                    f"(from {earliest.date().isoformat()})"
                ),
            )
    order = repo.create_order(
        case_id,
        package_code=payload.package_code,
        amount_rub=payload.amount_rub,
        status_value=payload.status,
        actor_id=principal.user_id,
        due_at=payload.due_at,
        service_label=payload.service_label,
        invoice_status=payload.invoice_status,
    )
    case = repo.require_case(principal, case_id)
    _push_case_crm(case, task=f"order:{payload.package_code}")
    return order


@router.post("/admin/cases/{case_id}/service-consent")
def record_service_consent(
    case_id: str,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Зафиксировать согласие клиента на услугу (для создания счёта)."""
    if principal.role not in (StaffRole.OPERATOR, StaffRole.ADMIN, StaffRole.EXPERT):
        raise HTTPException(status_code=403, detail="forbidden")
    repo = _repo()
    repo.require_case(principal, case_id)
    repo.audit(case_id, principal.audit_actor_id(), "service_consent_recorded")
    return {"ok": True, "action": "service_consent_recorded"}


@router.get("/admin/cases/{case_id}/marketing-consent")
def get_marketing_consent(
    case_id: str,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Статус marketing consent по каналам (не путать с ПДн)."""
    if principal.role not in (StaffRole.OPERATOR, StaffRole.ADMIN, StaffRole.EXPERT):
        raise HTTPException(status_code=403, detail="forbidden")
    from sfrfr.db.marketing_consent_repository import MarketingConsentRepository

    repo = _repo()
    case = repo.require_case(principal, case_id)
    client = case.get("clients") or {}
    try:
        summary = MarketingConsentRepository().status_summary(
            max_user_id=str(client.get("max_user_id") or "") or None,
            email=str(client.get("email") or "") or None,
            client_id=str(client.get("id") or "") or None,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "channels": {}}
    return {"ok": True, **summary}


@router.post("/admin/cases/{case_id}/marketing-consent/request")
def request_marketing_consent_max(
    case_id: str,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Отправить в MAX запрос согласия на рекламу (кнопки Да/Нет)."""
    if principal.role not in (StaffRole.OPERATOR, StaffRole.ADMIN, StaffRole.EXPERT):
        raise HTTPException(status_code=403, detail="forbidden")
    from sfrfr.integrations.max.marketing_consent_flow import (
        ASK_MARKETING_CONSENT_TEXT,
        marketing_consent_ask_keyboard,
    )

    repo = _repo()
    case = repo.require_case(principal, case_id)
    client = case.get("clients") or {}
    max_uid = str(client.get("max_user_id") or "").strip()
    if not max_uid:
        raise HTTPException(status_code=400, detail="client_has_no_max_user_id")
    text = ASK_MARKETING_CONSENT_TEXT
    attachments = marketing_consent_ask_keyboard()
    try:
        inserted = (
            get_supabase_client()
            .table("case_messages")
            .insert(
                {
                    "case_id": case_id,
                    "author_kind": "system",
                    "author_user_id": principal.user_id,
                    "body": text,
                    "channel_origin": "admin",
                }
            )
            .execute()
        )
        message_id = str((inserted.data or [{}])[0].get("id") or "").strip() or None
        from sfrfr.services.case_chat_delivery import (
            enqueue_max_delivery,
            process_pending_outbox,
        )

        if not enqueue_max_delivery(
            case_id=case_id,
            message_id=message_id,
            max_user_id=max_uid,
            body=text,
            attachments=attachments,
        ):
            raise RuntimeError("case_chat_outbox_enqueue_failed")
        process_pending_outbox(limit=5)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=(
                "Не удалось поставить сообщение общего чата в очередь. "
                "Повторите позже."
            ),
        ) from exc
    repo.audit(case_id, principal.audit_actor_id(), "marketing_consent_requested")
    return {
        "ok": True,
        "action": "marketing_consent_requested",
        "channel": "max",
        "queued": True,
    }


@router.get("/admin/finance")
def admin_finance(
    queue: str | None = Query(default=None, max_length=32),
    q: str | None = Query(default=None, max_length=120),
    package_code: str | None = None,
    period: str | None = Query(default=None, max_length=16),
    include_test: bool = False,
    principal: Principal = Depends(require_staff),
) -> dict:
    if principal.role is StaffRole.OPERATOR:
        raise HTTPException(status_code=403, detail="expert or admin role required")
    repo = _repo()
    cases = repo.list_cases(principal)
    case_ids = {str(c["id"]) for c in cases}
    orders = [o for o in repo.list_all_orders() if str(o.get("case_id")) in case_ids]
    snap = build_finance_snapshot(
        orders=orders,
        cases=cases,
        queue=queue,
        include_test=include_test,
        period=period,
        package_code=package_code,
        q=q,
    )
    snap["can_manage"] = principal.role is StaffRole.ADMIN
    return snap


def _require_order(
    principal: Principal, order_id: str
) -> tuple[CaseRepository, dict[str, Any], dict[str, Any]]:
    repo = _repo()
    order = repo.get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    case = repo.require_case(principal, str(order.get("case_id") or ""))
    return repo, order, case


@router.post("/admin/orders/{order_id}/pay-link")
def admin_order_pay_link(
    order_id: str,
    payload: FinancePayLinkRequest | None = None,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    if principal.role is StaffRole.OPERATOR:
        raise HTTPException(status_code=403, detail="expert or admin role required")
    from sfrfr.api.routes.payments import _return_url
    from sfrfr.services.pay_link import PayLinkError, issue_and_deliver_pay_link

    repo, order, case = _require_order(principal, order_id)
    case_id = str(order.get("case_id"))
    send_max = bool(payload.send_max) if payload else False
    try:
        result = issue_and_deliver_pay_link(
            repo=repo,
            order=order,
            case=case,
            actor_id=principal.user_id,
            send_max=send_max,
            channel="max" if send_max else "web_cabinet",
            return_url=_return_url(case_id, "web_cabinet"),
        )
    except PayLinkError as exc:
        if exc.code == "order_already_paid":
            raise HTTPException(status_code=400, detail="order already paid") from exc
        if exc.code == "client_has_no_max_user_id":
            raise HTTPException(status_code=400, detail="client_has_no_max_user_id") from exc
        if exc.code == "max_send_failed":
            raise HTTPException(
                status_code=502,
                detail=(
                    "Не удалось отправить сообщение в MAX. "
                    "Проверьте связь клиента с ботом и повторите."
                ),
            ) from exc
        raise HTTPException(status_code=400, detail=exc.code) from exc
    serialized = serialize_order(result["order"], case)
    return {
        "pay_url": result["pay_url"],
        "qr_url": serialized.get("qr_url") or result.get("qr_url"),
        "sent": result["sent"],
        "order": serialized,
    }


@router.post("/admin/orders/{order_id}/remind")
def admin_order_remind(
    order_id: str,
    payload: FinanceRemindRequest,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    if principal.role is StaffRole.OPERATOR:
        raise HTTPException(status_code=403, detail="expert or admin role required")
    repo, order, case = _require_order(principal, order_id)
    service = staff_package_label(str(order.get("package_code") or ""), order.get("service_label"))
    text = reminder_draft_text(
        service=service,
        amount_rub=float(order.get("amount_rub") or 0),
        pay_url=order.get("pay_url"),
    )
    sent = False
    if payload.send_max:
        from sfrfr.services.pay_link import (
            PayLinkError,
            is_yookassa_pay_url,
            issue_and_deliver_pay_link,
            public_qr_url,
            send_pay_link_max,
        )

        client = case.get("clients") or {}
        max_uid = str(client.get("max_user_id") or "").strip()
        if not max_uid:
            raise HTTPException(status_code=400, detail="client_has_no_max_user_id")
        pay_url = str(order.get("pay_url") or "")
        try:
            if not is_yookassa_pay_url(pay_url):
                # Нет живой ссылки ЮKassa — выставим счёт и отправим кнопку+QR
                from sfrfr.api.routes.payments import _return_url

                result = issue_and_deliver_pay_link(
                    repo=repo,
                    order=order,
                    case=case,
                    actor_id=principal.user_id,
                    send_max=True,
                    channel="max",
                    return_url=_return_url(str(order.get("case_id")), "web_cabinet"),
                )
                pay_url = str(result["pay_url"])
                text = reminder_draft_text(
                    service=service,
                    amount_rub=float(order.get("amount_rub") or 0),
                    pay_url=pay_url,
                )
            else:
                send_pay_link_max(
                    max_user_id=max_uid,
                    service=service,
                    amount_rub=float(order.get("amount_rub") or 0),
                    pay_url=pay_url,
                    qr_url=public_qr_url(order_id),
                    case_id=str(order.get("case_id") or ""),
                )
            sent = True
        except PayLinkError as exc:
            if exc.code == "client_has_no_max_user_id":
                raise HTTPException(status_code=400, detail=exc.code) from exc
            if exc.code == "max_send_failed":
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Не удалось отправить сообщение в MAX. "
                        "Проверьте связь клиента с ботом и повторите."
                    ),
                ) from exc
            raise HTTPException(status_code=400, detail=exc.code) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=502,
                detail=(
                    "Не удалось отправить сообщение в MAX. "
                    "Проверьте связь клиента с ботом и повторите."
                ),
            ) from exc
    repo.update_order_fields(
        order_id,
        case_id=str(order.get("case_id")),
        actor_id=principal.user_id,
        action="payment_reminder",
        fields={"reminder_draft": text, "next_action": "Проверить оплату"},
        audit_payload={"channel": payload.channel, "sent": sent},
    )
    due = order.get("due_at")
    if due:
        repo.upsert_checklist_item(
            str(order.get("case_id")),
            title="Проверить оплату",
            item_type="payment",
            owner="expert",
            actor_id=principal.user_id,
            due_at=str(due),
        )
    return {"reminder_draft": text, "sent": sent}


@router.post("/admin/orders/{order_id}/mark-paid")
def admin_order_mark_paid(
    order_id: str,
    payload: ManualPaymentRequest,
    principal: Principal = Depends(require_admin),
) -> dict[str, Any]:
    repo, order, case = _require_order(principal, order_id)
    if order.get("status") == "paid":
        raise HTTPException(status_code=400, detail="order already paid")
    expected = float(order.get("amount_rub") or 0)
    if payload.amount_rub + 0.009 < expected:
        updated = repo.update_order_fields(
            order_id,
            case_id=str(order.get("case_id")),
            actor_id=principal.user_id,
            action="partial_payment",
            fields={
                "invoice_status": "partially_paid",
                "next_action": "Решить вручную: частичная оплата",
            },
            audit_payload={
                "paid_at": payload.paid_at,
                "amount_rub": payload.amount_rub,
                "method": payload.method,
                "reference": payload.reference,
            },
        )
        from sfrfr.services.finance_automation import PARTIAL_TITLE, ensure_staff_task

        ensure_staff_task(
            repo,
            str(order.get("case_id")),
            title=PARTIAL_TITLE,
            item_type="payment",
            due_at=None,
            actor_id=principal.user_id,
            note="Полный этап не запускаем до полной оплаты.",
        )
        return {"order": serialize_order(updated, case), "partial": True}
    provider_payment_id = f"manual:{order_id}:{payload.reference[:40]}"
    repo.create_payment_record(
        order_id=order_id,
        case_id=str(order.get("case_id")),
        provider=f"manual:{payload.method}",
        provider_payment_id=provider_payment_id,
        status_value="pending",
        actor_id=principal.user_id,
    )
    repo.apply_provider_payment(
        provider_payment_id=provider_payment_id,
        status_value="succeeded",
        order_id=order_id,
        paid=True,
        package_code=str(order.get("package_code") or ""),
        case_id=str(order.get("case_id")),
    )
    repo.update_order_fields(
        order_id,
        case_id=str(order.get("case_id")),
        actor_id=principal.user_id,
        action="manual_paid",
        fields={"invoice_status": "paid"},
        audit_payload={
            "paid_at": payload.paid_at,
            "amount_rub": payload.amount_rub,
            "method": payload.method,
            "reference": payload.reference,
        },
    )
    refreshed = repo.get_order_by_id(order_id) or order
    return {"order": serialize_order(refreshed, case), "partial": False}


@router.post("/admin/orders/{order_id}/cancel")
def admin_order_cancel(
    order_id: str,
    payload: CancelOrderRequest,
    principal: Principal = Depends(require_admin),
) -> dict[str, Any]:
    repo, order, case = _require_order(principal, order_id)
    if order.get("status") == "paid":
        raise HTTPException(status_code=400, detail="cannot cancel paid order")
    updated = repo.update_order_fields(
        order_id,
        case_id=str(order.get("case_id")),
        actor_id=principal.user_id,
        action="order_cancelled",
        fields={
            "status": "cancelled",
            "invoice_status": "cancelled",
            "cancel_reason": payload.reason,
            "next_action": "Счёт отменён",
        },
        audit_payload={"reason": payload.reason, "comment": payload.comment},
    )
    return {"order": serialize_order(updated, case)}


@router.get("/admin/orders/{order_id}/audit")
def admin_order_audit(
    order_id: str,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    if principal.role is StaffRole.OPERATOR:
        raise HTTPException(status_code=403, detail="expert or admin role required")
    _repo_obj, _order, _case = _require_order(principal, order_id)
    rows = _repo_obj.list_finance_audit(order_id)
    return {"items": rows}


@router.get("/admin/analytics")
def admin_analytics(
    principal: Principal = Depends(require_staff),
    period: str = Query("30d"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    channel: str | None = Query(None),
    package_code: str | None = Query(None),
    pipeline_status: str | None = Query(None),
) -> dict:
    if principal.role is StaffRole.OPERATOR:
        raise HTTPException(status_code=403, detail="expert or admin role required")
    repo = _repo()
    cases = repo.list_analytics_cases(principal)
    case_ids = {str(c["id"]) for c in cases}
    orders = [o for o in repo.list_all_orders() if str(o.get("case_id")) in case_ids]
    return build_admin_analytics(
        cases=cases,
        orders=orders,
        period=period,
        date_from=date_from,
        date_to=date_to,
        channel=channel,
        package_code=package_code,
        pipeline_status=pipeline_status,
        include_finance=principal.role is StaffRole.ADMIN,
    )


@router.get("/admin/analytics/export")
def admin_analytics_export(
    principal: Principal = Depends(require_staff),
    format: Literal["csv", "json"] = Query("json"),
    period: str = Query("30d"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    channel: str | None = Query(None),
    package_code: str | None = Query(None),
    pipeline_status: str | None = Query(None),
) -> Response:
    if principal.role is StaffRole.OPERATOR:
        raise HTTPException(status_code=403, detail="expert or admin role required")
    repo = _repo()
    cases = repo.list_analytics_cases(principal)
    case_ids = {str(c["id"]) for c in cases}
    orders = [o for o in repo.list_all_orders() if str(o.get("case_id")) in case_ids]
    rows = analytics_export_rows(
        cases=cases,
        orders=orders,
        period=period,
        date_from=date_from,
        date_to=date_to,
        channel=channel,
        package_code=package_code,
        pipeline_status=pipeline_status,
    )
    filter_note = ":".join(
        part
        for part in (
            period,
            channel or "-",
            package_code or "-",
            pipeline_status or "-",
        )
    )
    repo.audit(
        "analytics",
        principal.user_id,
        f"analytics_export:{format}:{filter_note}:rows={len(rows)}",
    )
    if format == "csv":
        body = rows_to_csv(rows)
        media_type = "text/csv; charset=utf-8"
        filename = "sfrfr-analytics.csv"
    else:
        body = rows_to_json(rows)
        media_type = "application/json; charset=utf-8"
        filename = "sfrfr-analytics.json"
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/admin/cases/{case_id}/knowledge-feedback", status_code=201)
def knowledge_feedback(
    case_id: str,
    payload: KnowledgeFeedbackRequest,
    principal: Principal = Depends(require_staff),
) -> dict:
    """Сохранить feedback в БД и синхронизировать обезличенный кейс RAG (ТЗ-08)."""
    from sfrfr.ai.knowledge.feedback import apply_expert_feedback

    _require_expert(principal)
    repo = _repo()
    case = repo.require_case(principal, case_id)
    row = repo.save_knowledge_feedback(
        case_id,
        actor_id=principal.user_id,
        what_worked=payload.what_worked,
        documents_note=payload.documents_note,
        sfr_outcome=payload.sfr_outcome,
        quality=payload.quality,
    )
    kb = apply_expert_feedback(
        ops_case_id=case_id,
        quality=payload.quality,
        what_worked=payload.what_worked,
        documents_note=payload.documents_note,
        sfr_outcome=payload.sfr_outcome,
        problem_type=str(case.get("problem_type") or "expert_feedback"),
    )
    return {
        "feedback": row,
        "knowledge_case": {
            "case_id": kb.case_id,
            "quality": kb.quality.value,
            "rag_ready": kb.is_rag_ready(),
            "verified_at": kb.verified_at.isoformat() if kb.verified_at else None,
        },
    }


@router.get("/admin/knowledge-cases")
def list_knowledge_cases(
    principal: Principal = Depends(require_staff),
    rag_ready_only: bool = Query(default=False),
) -> dict:
    """Реестр обезличенных кейсов (без ПДн) для эксперта/админа."""
    from sfrfr.ai.knowledge.registry import KnowledgeCaseRegistry

    if principal.role is StaffRole.OPERATOR:
        raise HTTPException(status_code=403, detail="expert or admin role required")
    cases = KnowledgeCaseRegistry().list_cases(rag_ready_only=rag_ready_only)
    return {
        "cases": [
            {
                "case_id": c.case_id,
                "quality": c.quality.value,
                "problem_type": c.problem_type,
                "sfr_outcome": c.sfr_outcome.value,
                "rag_ready": c.is_rag_ready(),
                "verified_at": c.verified_at.isoformat() if c.verified_at else None,
                "ops_case_id": c.ops_case_id,
                "summary": c.summary[:300],
            }
            for c in cases
        ],
        "note": "В RAG только verified и template.",
    }


@router.get("/admin/staff-roles")
def list_staff_roles(principal: Principal = Depends(require_admin)) -> list[dict]:
    """Совместимость: обёртка над GET /admin/staff."""
    from sfrfr.db.staff_access import list_staff_members

    return list_staff_members()


@router.get("/admin/staff")
def list_staff(principal: Principal = Depends(require_admin)) -> list[dict]:
    from sfrfr.db.staff_access import list_staff_members

    return list_staff_members()


@router.post("/admin/staff/invites")
def invite_staff(
    payload: StaffInviteRequest,
    request: Request,
    principal: Principal = Depends(require_admin),
) -> dict:
    from sfrfr.db.staff_access import invite_staff_member

    return invite_staff_member(
        actor_id=principal.user_id,
        email=payload.email,
        display_name=payload.display_name,
        role=payload.role.value,
        confirm_admin_grant=payload.confirm_admin_grant,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/admin/staff/invites/{user_id}/revoke")
def revoke_staff_invite(
    user_id: str,
    request: Request,
    principal: Principal = Depends(require_admin),
) -> dict:
    from sfrfr.db.staff_access import revoke_invite

    return revoke_invite(
        actor_id=principal.user_id,
        target_user_id=user_id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.patch("/admin/staff/{user_id}")
def patch_staff(
    user_id: str,
    payload: StaffPatchRequest,
    request: Request,
    principal: Principal = Depends(require_admin),
) -> dict:
    from sfrfr.db.staff_access import patch_staff_member

    return patch_staff_member(
        actor_id=principal.user_id,
        target_user_id=user_id,
        role=payload.role.value if payload.role is not None else None,
        status_value=payload.status,
        display_name=payload.display_name,
        confirm_admin_grant=payload.confirm_admin_grant,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/admin/staff/{user_id}/audit")
def staff_member_audit(
    user_id: str,
    principal: Principal = Depends(require_admin),
) -> list[dict]:
    from sfrfr.db.staff_access import list_staff_audit

    return list_staff_audit(user_id)


@router.put("/admin/staff-roles/{user_id}")
def upsert_staff_role(
    user_id: str,
    payload: StaffRoleUpsert,
    request: Request,
    principal: Principal = Depends(require_admin),
) -> dict:
    """Legacy upsert по UUID — только смена роли существующего сотрудника."""
    from sfrfr.db.staff_access import get_staff_row, patch_staff_member

    if get_staff_row(user_id) is None:
        raise HTTPException(
            status_code=400,
            detail="Создание роли по UUID отключено. Используйте POST /admin/staff/invites",
        )
    return patch_staff_member(
        actor_id=principal.user_id,
        target_user_id=user_id,
        role=payload.role.value,
        confirm_admin_grant=payload.confirm_admin_grant,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
