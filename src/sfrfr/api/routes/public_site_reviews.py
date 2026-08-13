"""Публичные цитаты для витрины + очередь (без рейтинга)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from sfrfr.api.routes.public_leads import _require_captcha
from sfrfr.core.site_reviews import enqueue_quote, list_published

router = APIRouter()


class SiteReviewSubmit(BaseModel):
    """Короткий отзыв с /otzyvy/: без ФИО, в очередь модерации."""

    text: str = Field(min_length=1, max_length=600)
    consent: bool = Field(description="Согласие на показ текста на сайте без ФИО")
    smartcaptcha_token: str | None = Field(default=None, max_length=4000)
    recaptcha_token: str | None = Field(default=None, max_length=4000)


@router.get("/site-reviews")
def public_site_reviews(limit: int = 6) -> dict[str, Any]:
    """Только published — для блока на главной и /otzyvy/."""
    items = list_published(limit=limit)
    return {
        "ok": True,
        "items": items,
        "note": "Рейтинг только на Яндекс Картах; здесь модерируемые цитаты.",
    }


@router.post("/site-reviews")
def submit_site_review(payload: SiteReviewSubmit, request: Request) -> dict[str, Any]:
    """Поставить цитату в очередь. На рейтинг Яндекса не влияет."""
    if not payload.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="consent_required",
        )
    client_ip = request.client.host if request.client else None
    _require_captcha(
        recaptcha_token=payload.recaptcha_token,
        smartcaptcha_token=payload.smartcaptcha_token,
        client_ip=client_ip,
    )
    result = enqueue_quote(text=payload.text, source="site", consent=True)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="consent_required",
        )
    if not result.get("queued"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(result.get("reason") or "rejected"),
        )
    return {
        "ok": True,
        "queued": True,
        "detail": "После модерации появится на странице.",
    }
