from pydantic import BaseModel, Field

from sfrfr.ai.schemas.agents import DraftResult, Finding
from sfrfr.models.case_status import CaseStatus


class CaseCreate(BaseModel):
    client_name: str = Field(min_length=1, max_length=200)
    snils_masked: str = Field(description="Маскированный СНИЛС, без полного номера в логах")
    consent_given: bool = True


class CaseRead(BaseModel):
    id: str
    client_name: str
    snils_masked: str
    status: CaseStatus
    document_count: int = 0
    ocr_count: int = 0
    findings: list[Finding] = Field(default_factory=list)
    draft: DraftResult | None = None
    error: str | None = None


class AdvanceResponse(BaseModel):
    ok: bool
    message: str
    case: CaseRead
