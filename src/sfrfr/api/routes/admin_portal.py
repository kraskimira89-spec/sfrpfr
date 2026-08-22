"""Admin/expert API: дашборд, реестр, карточка, финансы, роли (ТЗ-04 + каналы ТЗ-09)."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from sfrfr.api.schemas.admin import (
    AssignExpertRequest,
    CaseNextActionUpdate,
    ChecklistItemCreate,
    ChecklistItemUpdate,
    DashboardResponse,
    KnowledgeFeedbackRequest,
    MaxReplyRequest,
    OrderCreateRequest,
    ResultConfirmRequest,
    StaffCaseSummary,
    StaffRoleUpsert,
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
from sfrfr.services.staff_work_queue import (
    build_dashboard_snapshot,
    build_work_item,
    derive_next_action,
    derive_waiting_on,
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
    )


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
        "next_action": case.get("next_action"),
        "next_action_at": case.get("next_action_at"),
        "waiting_on": case.get("waiting_on") or derive_waiting_on(case),
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
        "documents": [
            {
                "id": d.get("id"),
                "storage_path": d.get("storage_path"),
                "doc_type": d.get("doc_type"),
                "created_at": d.get("created_at"),
            }
            for d in (case.get("documents") or [])
        ],
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
        "warning": (
            "Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. "
            "Решение принимает СФР. Результат не гарантирован."
        ),
        "role_capabilities": {
            "can_edit_pipeline": principal.role in (StaffRole.EXPERT, StaffRole.ADMIN),
            "can_edit_checklist": principal.role in (StaffRole.EXPERT, StaffRole.ADMIN),
            "can_confirm_result": principal.role in (StaffRole.EXPERT, StaffRole.ADMIN),
            "can_manage_orders": principal.role is StaffRole.ADMIN,
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
    principal: Principal = Depends(require_staff),
) -> list[StaffCaseSummary]:
    cases = _repo().list_cases(principal)
    needle = (q or "").strip().lower()
    result: list[StaffCaseSummary] = []
    for case in cases:
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
        result.append(_staff_summary(case, role=principal.role))
    return result


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
        payload["orders"] = repo.list_orders(case_id)
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


@router.patch("/admin/cases/{case_id}/assign-expert")
def assign_expert(
    case_id: str,
    payload: AssignExpertRequest,
    principal: Principal = Depends(require_staff),
) -> dict:
    if principal.role not in (StaffRole.OPERATOR, StaffRole.ADMIN):
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
    from sfrfr.integrations.max.client import MaxBotClient

    repo = _repo()
    case = repo.require_case(principal, case_id)
    client = case.get("clients") or {}
    max_uid = str(client.get("max_user_id") or "").strip()
    if not max_uid:
        raise HTTPException(status_code=400, detail="client_has_no_max_user_id")
    bot = MaxBotClient()
    if not bot.available:
        raise HTTPException(status_code=503, detail="max_bot_not_configured")
    try:
        result = bot.send_message(text=payload.message.strip(), user_id=max_uid)
    except Exception as exc:  # noqa: BLE001
        detail = f"max_send_failed:{type(exc).__name__}"
        raise HTTPException(status_code=502, detail=detail) from exc
    repo.audit(case_id, principal.audit_actor_id(), "staff_max_reply_sent")
    return {"ok": True, "max_user_id": max_uid, "result": result}


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
    principal: Principal = Depends(require_admin),
) -> dict:
    repo = _repo()
    repo.require_case(principal, case_id)
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
    )
    case = repo.require_case(principal, case_id)
    _push_case_crm(case, task=f"order:{payload.package_code}")
    return order


@router.get("/admin/finance")
def admin_finance(principal: Principal = Depends(require_staff)) -> dict:
    if principal.role is StaffRole.OPERATOR:
        raise HTTPException(status_code=403, detail="expert or admin role required")
    repo = _repo()
    cases = repo.list_cases(principal)
    case_ids = {str(c["id"]) for c in cases}
    orders = [o for o in repo.list_all_orders() if str(o.get("case_id")) in case_ids]
    return {
        "orders": orders,
        "formula": "10% ЕДВ + 50% прибавки за 3 месяца",
        "post_payment_delay_days_min": SUCCESS_FEE_DELAY_DAYS_MIN,
    }


@router.get("/admin/analytics")
def admin_analytics(principal: Principal = Depends(require_staff)) -> dict:
    if principal.role is StaffRole.OPERATOR:
        raise HTTPException(status_code=403, detail="expert or admin role required")
    rows = _repo().anonymized_analytics_rows()
    if principal.role is StaffRole.EXPERT:
        allowed = {str(c["id"]) for c in _repo().list_cases(principal)}
        rows = [r for r in rows if r["case_id"] in allowed]
    return {
        "rows": rows,
        "note": "Обезличенная выборка без ФИО, контактов, СНИЛС, файлов и распознанного текста.",
        "aggregates": {
            "cases": len(rows),
            "paid_diag": sum(1 for r in rows if r["paid_diag"]),
            "paid_service": sum(1 for r in rows if r["paid_service"]),
            "result_up": sum(1 for r in rows if r["result_band"] == "up"),
            "by_channel": dict(Counter(r["preferred_channel"] for r in rows)),
        },
    }


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
    return _repo().list_staff_roles()


@router.put("/admin/staff-roles/{user_id}")
def upsert_staff_role(
    user_id: str,
    payload: StaffRoleUpsert,
    principal: Principal = Depends(require_admin),
) -> dict:
    return _repo().upsert_staff_role(user_id, payload.role.value, principal.user_id)
