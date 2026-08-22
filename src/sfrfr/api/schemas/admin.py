"""Контракты admin/expert API (ТЗ-04 + каналы ТЗ-09)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from sfrfr.models.case_status import CaseStatus
from sfrfr.security.auth import StaffRole


class StaffCaseSummary(BaseModel):
    id: str
    pipeline_status: CaseStatus | str
    b2c_status: str
    created_at: str | None = None
    first_contact_at: str | None = None
    expert_user_id: str | None = None
    checklist_open_count: int = 0
    client_name: str | None = None
    client_phone: str | None = None
    crm_external_id: str | None = None
    crm_url: str | None = None
    meeting_url: str | None = None
    preferred_channel: str = "unset"
    max_linked: bool = False
    web_linked: bool = False
    silent_days: int = 0
    package_codes: list[str] = Field(default_factory=list)
    next_action: str | None = None
    next_action_at: str | None = None
    waiting_on: str | None = None
    priority: str | None = None
    deadline_status: str | None = None
    is_test: bool = False
    last_event: str | None = None


class WorkQueueItem(BaseModel):
    case_id: str
    client_name: str | None = None
    priority: Literal["urgent", "today", "standard"]
    pipeline_status: str
    b2c_status: str = ""
    waiting_on: str
    last_event: str
    next_action: str
    next_action_at: str | None = None
    deadline_status: Literal["overdue", "soon", "today", "ok", "waiting"]
    channel: str = "unset"
    expert_user_id: str | None = None
    doc_flags: dict[str, bool] = Field(default_factory=dict)


class CaseFlagsUpdate(BaseModel):
    is_test: bool


class CaseNextActionUpdate(BaseModel):
    next_action: str | None = Field(default=None, max_length=500)
    next_action_at: str | None = None
    waiting_on: Literal["staff", "client", "archive", "sfr", "payment", "none"] | None = None


class DashboardResponse(BaseModel):
    new_leads: int
    by_pipeline: dict[str, int]
    by_b2c: dict[str, int]
    payments_pending: int
    payments_paid: int
    silent: dict[str, int]
    channel_conflicts: int
    unlinked_max: int
    unlinked_web: int
    needs_reply: int = 0
    needs_reply_over_30m: int = 0
    deadline_today: int = 0
    waiting_docs: int = 0
    waiting_docs_max_days: int = 0
    sla_risk: int = 0
    greeting_priority_count: int = 0
    payments_pending_amount: float = 0
    payments_paid_today: int = 0
    payments_paid_today_amount: float = 0
    sla_control: dict[str, int] = Field(default_factory=dict)
    doc_status: dict[str, int] = Field(default_factory=dict)
    work_queue: list[WorkQueueItem] = Field(default_factory=list)
    my_tasks_today: list[WorkQueueItem] = Field(default_factory=list)


class ChecklistItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    item_type: str = Field(default="action", max_length=64)
    owner: Literal["client", "expert"] = "client"
    due_at: str | None = None
    note: str | None = Field(default=None, max_length=2000)
    sort_order: int = 0


class ChecklistItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    status: Literal["open", "done", "blocked", "cancelled"] | None = None
    note: str | None = Field(default=None, max_length=2000)
    due_at: str | None = None


class ResultConfirmRequest(BaseModel):
    monthly_before_rub: float = Field(ge=0)
    monthly_after_rub: float = Field(ge=0)
    lump_sum_rub: float = Field(default=0, ge=0)
    result_effective_at: str | None = None


class OrderCreateRequest(BaseModel):
    package_code: Literal["DIAG", "ACCOMP", "SF_LUMP", "SF_MONTH"]
    amount_rub: float = Field(gt=0)
    status: Literal["draft", "pending", "paid", "cancelled"] = "pending"
    due_at: str | None = None
    service_label: str | None = Field(default=None, max_length=200)
    invoice_status: str | None = Field(default=None, max_length=40)


class ManualPaymentRequest(BaseModel):
    paid_at: str
    amount_rub: float = Field(gt=0)
    method: Literal["card", "transfer", "cash", "yookassa", "other"]
    reference: str = Field(min_length=1, max_length=200)


class CancelOrderRequest(BaseModel):
    reason: Literal["refusal", "duplicate", "amount_error", "no_contact", "other"]
    comment: str | None = Field(default=None, max_length=500)


class FinancePayLinkRequest(BaseModel):
    send_max: bool = False


class FinanceRemindRequest(BaseModel):
    send_max: bool = False
    channel: Literal["max", "email", "web"] = "max"


class YandexMailRequest(BaseModel):
    template: Literal["request_docs", "reminder", "custom"] = "request_docs"
    to: str | None = Field(default=None, max_length=200)
    subject: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=4000)


class MaxReplyRequest(BaseModel):
    message: str = Field(min_length=1, max_length=3500)


class KnowledgeFeedbackRequest(BaseModel):
    what_worked: str | None = Field(default=None, max_length=4000)
    documents_note: str | None = Field(default=None, max_length=4000)
    sfr_outcome: str | None = Field(default=None, max_length=500)
    quality: Literal["draft", "verified", "template", "rejected"] = "draft"


class StaffRoleUpsert(BaseModel):
    role: StaffRole
    confirm_admin_grant: bool = False


class StaffInviteRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)
    role: StaffRole
    confirm_admin_grant: bool = False


class StaffPatchRequest(BaseModel):
    role: StaffRole | None = None
    status: Literal["active", "invited", "suspended", "archived"] | None = None
    display_name: str | None = Field(default=None, max_length=200)
    confirm_admin_grant: bool = False


class AssignExpertRequest(BaseModel):
    expert_user_id: str | None = None
