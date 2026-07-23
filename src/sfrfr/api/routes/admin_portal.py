"""Admin/expert API: дашборд, реестр, карточка, финансы, роли (ТЗ-04 + каналы ТЗ-09)."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from sfrfr.api.schemas.admin import (
    AssignExpertRequest,
    ChecklistItemCreate,
    ChecklistItemUpdate,
    DashboardResponse,
    KnowledgeFeedbackRequest,
    OrderCreateRequest,
    ResultConfirmRequest,
    StaffCaseSummary,
    StaffRoleUpsert,
)
from sfrfr.api.schemas.portal import CaseStatusUpdate, CaseSummary
from sfrfr.core.config import get_settings
from sfrfr.core.success_fee import (
    SUCCESS_FEE_DELAY_DAYS_MIN,
    calc_success_fee,
)
from sfrfr.db.case_repository import CaseRepository
from sfrfr.db.session import get_supabase_client
from sfrfr.integrations.sheets import SheetsExporter, sanitize_rows
from sfrfr.integrations.taganay.sync import push_case_to_taganay
from sfrfr.security.auth import (
    Principal,
    StaffRole,
    require_admin,
    require_staff,
)

router = APIRouter()

_SILENT_BUCKETS = (30, 90, 150, 180)


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
    template = get_settings().taganay_case_url_template
    if "{id}" in template:
        return template.replace("{id}", crm_external_id)
    return template.rstrip("/") + f"?case_id={crm_external_id}"


def _staff_summary(case: dict[str, Any], *, role: StaffRole | None) -> StaffCaseSummary:
    client = case.get("clients") or {}
    checklist = case.get("checklist_items") or []
    orders = case.get("orders") or []
    show_contact = role in (StaffRole.OPERATOR, StaffRole.ADMIN, StaffRole.EXPERT)
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
        preferred_channel=client.get("preferred_channel") or "unset",
        max_linked=bool(client.get("max_user_id")),
        web_linked=bool(client.get("user_id")),
        silent_days=_silent_days(case),
        package_codes=[str(o.get("package_code")) for o in orders if o.get("package_code")],
    )


def _filter_staff_case(case: dict[str, Any], principal: Principal) -> dict[str, Any]:
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
            "cabinet_url": f"{settings.cabinet_public_url.rstrip('/')}/?case={case['id']}",
            "max_bot_url": settings.max_public_bot_url,
            "max_miniapp_url": settings.max_miniapp_url,
        },
        "warning": "Решение принимает СФР. Результат не гарантирован.",
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
        pipeline = (
            get_supabase_client()
            .table("case_pipeline_data")
            .select("*")
            .eq("case_id", case["id"])
            .maybe_single()
            .execute()
            .data
        )
        base["pipeline_data"] = pipeline
        base["ocr_texts"] = (pipeline or {}).get("ocr_texts") or []
        base["ils_periods"] = (pipeline or {}).get("ils_periods") or []
        base["labor_periods"] = (pipeline or {}).get("labor_periods") or []
        base["findings"] = (pipeline or {}).get("findings") or []
        base["draft"] = (pipeline or {}).get("draft")
        base["classifications"] = (pipeline or {}).get("classifications") or []
    return base


@router.get("/admin/dashboard", response_model=DashboardResponse)
def admin_dashboard(principal: Principal = Depends(require_staff)) -> DashboardResponse:
    cases = _repo().list_cases(principal)
    by_pipeline = Counter(str(c.get("pipeline_status")) for c in cases)
    by_b2c = Counter(str(c.get("b2c_status")) for c in cases)
    silent = {str(days): 0 for days in _SILENT_BUCKETS}
    for case in cases:
        days = _silent_days(case)
        for bucket in reversed(_SILENT_BUCKETS):
            if days >= bucket:
                silent[str(bucket)] += 1
                break

    orders = _repo().list_all_orders() if principal.role is StaffRole.ADMIN else []
    # Эксперт/оператор считают оплаты только по своим делам
    if principal.role is not StaffRole.ADMIN:
        case_ids = {str(c["id"]) for c in cases}
        orders = [o for o in _repo().list_all_orders() if str(o.get("case_id")) in case_ids]

    pending = sum(1 for o in orders if o.get("status") == "pending")
    paid = sum(1 for o in orders if o.get("status") == "paid")

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
        # конфликт: предпочтение MAX без max_user_id или web без OTP
        preferred = client.get("preferred_channel") or "unset"
        if preferred == "max_miniapp" and not max_linked:
            channel_conflicts += 1
        if preferred == "web_cabinet" and not web_linked:
            channel_conflicts += 1

    return DashboardResponse(
        new_leads=by_b2c.get("lead", 0),
        by_pipeline=dict(by_pipeline),
        by_b2c=dict(by_b2c),
        payments_pending=pending,
        payments_paid=paid,
        silent=silent,
        channel_conflicts=channel_conflicts,
        unlinked_max=unlinked_max,
        unlinked_web=unlinked_web,
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
    payload = _filter_staff_case(case, principal)
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
    push_case_to_taganay(case, task=f"pipeline:{payload.pipeline_status.value}")
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
    push_case_to_taganay(case, task="result_confirmed")
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
    push_case_to_taganay(case, task=f"order:{payload.package_code}")
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
        "note": "Whitelist без ФИО/телефона/СНИЛС/файлов/OCR. Для выгрузки в Google Sheets.",
        "aggregates": {
            "cases": len(rows),
            "paid_diag": sum(1 for r in rows if r["paid_diag"]),
            "paid_service": sum(1 for r in rows if r["paid_service"]),
            "result_up": sum(1 for r in rows if r["result_band"] == "up"),
            "by_channel": dict(Counter(r["preferred_channel"] for r in rows)),
        },
    }


@router.post("/admin/analytics/sheets-sync")
def admin_analytics_sheets_sync(principal: Principal = Depends(require_admin)) -> dict:
    """Пуш обезличенных строк в Google Sheets webhook (ТЗ-06)."""
    rows = sanitize_rows(_repo().anonymized_analytics_rows())
    result = SheetsExporter().push(rows)
    return {"export": result, "rows": len(rows), "pii": False}


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
