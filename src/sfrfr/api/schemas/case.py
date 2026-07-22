from pydantic import BaseModel, Field

from sfrfr.ai.schemas.agents import DraftResult, Finding
from sfrfr.models.case_status import CaseStatus


class CaseCreate(BaseModel):
    client_name: str = Field(min_length=1, max_length=200)
    snils_masked: str = Field(description="Маскированный СНИЛС, без полного номера в логах")
    consent_given: bool = True


class CaseOpen(BaseModel):
    """Открыть существующее дело по MAX user или создать новое."""

    max_user_id: str = Field(min_length=1, max_length=64)
    client_name: str | None = Field(default=None, max_length=200)
    snils_masked: str = Field(default="***-***-*** **", max_length=32)
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
    max_user_id: str | None = None


class AdvanceResponse(BaseModel):
    ok: bool
    message: str
    case: CaseRead
