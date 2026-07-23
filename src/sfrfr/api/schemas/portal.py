"""Контракты защищённых клиентского и административного API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sfrfr.models.case_status import CaseStatus


class CaseSummary(BaseModel):
    id: str
    pipeline_status: CaseStatus | str
    b2c_status: str
    created_at: str | None = None
    expert_user_id: str | None = None
    checklist_open_count: int = 0


class CaseMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4_000)


class CaseStatusUpdate(BaseModel):
    pipeline_status: CaseStatus


class SignedDocumentResponse(BaseModel):
    url: str
    expires_in: int
