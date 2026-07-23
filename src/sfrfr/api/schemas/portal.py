"""Контракты защищённых клиентского и административного API."""

from __future__ import annotations

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


class ClientCaseDetail(BaseModel):
    """Клиентское представление дела без служебных OCR/findings."""

    id: str
    pipeline_status: CaseStatus | str
    b2c_status: str
    created_at: str | None = None
    expert_assigned: bool = False
    consent_accepted: bool = False
    checklist_items: list[dict[str, Any]] = Field(default_factory=list)
    required_documents: list[dict[str, Any]] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    draft: dict[str, Any] | None = None
    submission_instruction: str | None = None
    warning: str = (
        "Решение принимает СФР. Результат не гарантирован."
    )
