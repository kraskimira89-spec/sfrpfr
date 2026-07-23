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
    preferred_channel: str = "unset"
    max_linked: bool = False
    web_linked: bool = False
    silent_days: int = 0
    package_codes: list[str] = Field(default_factory=list)


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
    status: str = "pending"


class KnowledgeFeedbackRequest(BaseModel):
    what_worked: str | None = Field(default=None, max_length=4000)
    documents_note: str | None = Field(default=None, max_length=4000)
    sfr_outcome: str | None = Field(default=None, max_length=500)
    quality: Literal["draft", "verified", "template", "rejected"] = "draft"


class StaffRoleUpsert(BaseModel):
    role: StaffRole


class AssignExpertRequest(BaseModel):
    expert_user_id: str | None = None
