"""Публичный API: анкета отзыва → черновик (без автопубликации в Яндекс)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from sfrfr.api.routes.public_leads import _require_captcha
from sfrfr.core.review_draft import (
    QUESTIONS,
    build_review_draft,
    normalize_answers,
    question_catalog,
)
from sfrfr.core.site_reviews import enqueue_quote

router = APIRouter()


class ReviewDraftRequest(BaseModel):
    answers: dict[str, Any] = Field(
        default_factory=dict,
        description="question_id → option_id | list[option_id] | csv",
    )
    improve: str | None = Field(default=None, max_length=400)
    site_quote_consent: bool = Field(
        default=False,
        description="Можно показать цитату на сайте (в очередь модерации, не в рейтинг)",
    )
    smartcaptcha_token: str | None = Field(default=None, max_length=4000)
    recaptcha_token: str | None = Field(default=None, max_length=4000)


class ReviewDraftResponse(BaseModel):
    ok: bool
    draft: str = ""
    source: str = "none"
    publish_url: str = ""
    anketa_url: str = ""
    detail: str = ""
    quote_queued: bool = False
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

    allowed = {str(q["id"]) for q in QUESTIONS}
    raw = {k: v for k, v in (payload.answers or {}).items() if str(k) in allowed}
    cleaned = normalize_answers(raw)

    result = build_review_draft(cleaned, improve=payload.improve)
    if not result.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(result.get("error") or "bad_answers"),
        )

    draft = str(result.get("draft") or "")
    quote_queued = False
    if payload.site_quote_consent and draft:
        queued = enqueue_quote(text=draft, source="anketa", consent=True)
        quote_queued = bool(queued and queued.get("queued"))

    return ReviewDraftResponse(
        ok=True,
        draft=draft,
        source=str(result.get("source") or "template"),
        publish_url=str(result.get("publish_url") or ""),
        anketa_url=str(result.get("anketa_url") or ""),
        quote_queued=quote_queued,
    )
