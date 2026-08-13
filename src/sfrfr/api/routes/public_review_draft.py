"""Публичный API: анкета отзыва → черновик (без автопубликации в Яндекс)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from sfrfr.api.routes.public_leads import _require_captcha
from sfrfr.core.review_draft import QUESTIONS, build_review_draft, question_catalog

router = APIRouter()


class ReviewDraftRequest(BaseModel):
    answers: dict[str, str] = Field(
        default_factory=dict,
        description="Словарь question_id → option_id или короткий текст",
    )
    improve: str | None = Field(default=None, max_length=400)
    smartcaptcha_token: str | None = Field(default=None, max_length=4000)
    recaptcha_token: str | None = Field(default=None, max_length=4000)


class ReviewDraftResponse(BaseModel):
    ok: bool
    draft: str = ""
    source: str = "none"
    publish_url: str = ""
    anketa_url: str = ""
    detail: str = ""
    questions: list[dict[str, Any]] | None = None


@router.get("/review-draft/questions")
def review_draft_questions() -> dict[str, Any]:
    return {"ok": True, "questions": question_catalog()}


@router.post("/review-draft", response_model=ReviewDraftResponse)
def create_review_draft(payload: ReviewDraftRequest, request: Request) -> ReviewDraftResponse:
    client_ip = request.client.host if request.client else None
    _require_captcha(
        recaptcha_token=payload.recaptcha_token,
        smartcaptcha_token=payload.smartcaptcha_token,
        client_ip=client_ip,
    )

    # Только известные ключи вопросов + длина значений
    allowed = {str(q["id"]) for q in QUESTIONS}
    cleaned: dict[str, str] = {}
    for key, value in (payload.answers or {}).items():
        kid = str(key).strip()[:32]
        if kid not in allowed:
            continue
        cleaned[kid] = str(value or "").strip()[:200]

    result = build_review_draft(cleaned, improve=payload.improve)
    if not result.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(result.get("error") or "bad_answers"),
        )
    return ReviewDraftResponse(
        ok=True,
        draft=str(result.get("draft") or ""),
        source=str(result.get("source") or "template"),
        publish_url=str(result.get("publish_url") or ""),
        anketa_url=str(result.get("anketa_url") or ""),
    )
