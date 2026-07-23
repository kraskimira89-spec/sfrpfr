"""Контракты защищённых клиентского и административного API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from sfrfr.models.case_status import CaseStatus


class CaseSummary(BaseModel):
    id: str
    pipeline_status: CaseStatus | str
    b2c_status: str
    created_at: str | None = None
    expert_user_id: str | None = None
    expert_assigned: bool = False
    checklist_open_count: int = 0
    next_action: str | None = None
    unread_messages: int = 0
    consent_accepted: bool = False


class CaseMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4_000)


class CaseStatusUpdate(BaseModel):
    pipeline_status: CaseStatus


class SignedDocumentResponse(BaseModel):
    url: str
    expires_in: int


class ConsentAcceptRequest(BaseModel):
    version: str = Field(default="pdn-v1", min_length=1, max_length=64)


class ContractAcceptRequest(BaseModel):
    offer_version: str = Field(default="offer-v1", min_length=1, max_length=64)
    order_id: str | None = None


class PreferredChannel(StrEnum):
    MAX_MINIAPP = "max_miniapp"
    WEB_CABINET = "web_cabinet"
    UNSET = "unset"


class PortalMeResponse(BaseModel):
    user_id: str
    email: str | None = None
    client_id: str | None = None
    full_name: str | None = None
    role: str | None = None
    is_staff: bool = False
    preferred_channel: PreferredChannel = PreferredChannel.UNSET
    preferred_channel_set_at: str | None = None
    max_linked: bool = False
    web_linked: bool = True
    max_user_id: str | None = None
    cabinet_url: str
    max_bot_url: str
    max_miniapp_url: str


class PreferencesUpdateRequest(BaseModel):
    preferred_channel: PreferredChannel


class LinkMaxRequest(BaseModel):
    max_user_id: str | None = None
    init_data: str | None = None
    preferred_channel: PreferredChannel | None = None


class LinkWebFromMaxRequest(BaseModel):
    max_user_id: str | None = None
    init_data: str | None = None
    preferred_channel: PreferredChannel = PreferredChannel.MAX_MINIAPP


class LinkWebFromMaxResponse(BaseModel):
    client_id: str
    max_user_id: str
    cabinet_url: str
    message: str


class FindingItem(BaseModel):
    type: str = "info"
    detail: str = ""
    severity: str = "info"


class PipelineRunResponse(BaseModel):
    ok: bool
    message: str
    pipeline_status: str | None = None
    findings: list[FindingItem] = Field(default_factory=list)
    draft: dict[str, Any] | None = None
    warning: str = "Решение принимает СФР. Результат не гарантирован."


class ClientCaseDetail(BaseModel):
    """Клиентское представление дела (без сырого OCR)."""

    id: str
    pipeline_status: CaseStatus | str
    b2c_status: str
    created_at: str | None = None
    expert_assigned: bool = False
    consent_accepted: bool = False
    checklist_items: list[dict[str, Any]] = Field(default_factory=list)
    required_documents: list[dict[str, Any]] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[FindingItem] = Field(default_factory=list)
    draft: dict[str, Any] | None = None
    next_action: str | None = None
    status_label: str | None = None
    status_hint: str | None = None
    pipeline_error: str | None = None
    submission_instruction: str | None = None
    warning: str = (
        "Решение принимает СФР. Результат не гарантирован."
    )
