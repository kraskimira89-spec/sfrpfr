"""Публичные цитаты для витрины + очередь (без рейтинга)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from sfrfr.api.routes.public_leads import _require_captcha
from sfrfr.core.config import get_settings
from sfrfr.core.site_reviews import enqueue_quote, list_published

logger = logging.getLogger(__name__)

router = APIRouter()

_REVIEW_NOTIFY_EMAIL = "proverkastaza@yandex.ru"


class SiteReviewSubmit(BaseModel):
    """Короткий отзыв с /otzyvy/: без ФИО, в очередь модерации."""

    text: str = Field(min_length=1, max_length=600)
    consent: bool = Field(description="Согласие на показ текста на сайте без ФИО")
    smartcaptcha_token: str | None = Field(default=None, max_length=4000)
    recaptcha_token: str | None = Field(default=None, max_length=4000)
    mail_already_sent: bool = Field(
        default=False,
        description="True если письмо уже отправил CF7 — не дублировать SMTP",
    )
    source: str = Field(default="site", max_length=32)


def _trusted_wp_token(x_public_lead_token: str | None) -> bool:
    """WP MU после CF7: тот же PUBLIC_LEAD_TOKEN, что у заявок."""
    expected = (get_settings().public_lead_token or "").strip()
    if not expected or not x_public_lead_token:
        return False
    return x_public_lead_token.strip() == expected


def notify_site_review_queued(
    *,
    text: str,
    item_id: str,
    source: str,
    send_email: bool = True,
) -> dict[str, Any]:
    """Письмо на proverkastaza@yandex.ru (если нужно) + fanout в MAX / канал команды."""
    preview = (text or "").strip()
    if len(preview) > 280:
        preview = preview[:279] + "…"
    body = (
        "Новый отзыв на сайте (очередь модерации)\n"
        f"id: {item_id}\n"
        f"источник: {source}\n"
        f"текст: {preview}\n"
        "Одобрить: sfrfr site-reviews-set <id> --status published\n"
        "Отклонить: sfrfr site-reviews-set <id> --status rejected"
    )
    out: dict[str, Any] = {"email": None, "max": None}

    if send_email:
        try:
            from sfrfr.integrations.yandex_workspace.mail import send_mail

            out["email"] = send_mail(
                to=_REVIEW_NOTIFY_EMAIL,
                template="custom",
                subject="[Проверка стажа] Отзыв на сайте (модерация)",
                body=body,
                from_name="Проверка стажа",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("site review email notify failed: %s", exc)
            out["email"] = {"ok": False, "error": type(exc).__name__}

    try:
        from sfrfr.integrations.max.handler import _fanout_ops_text

        _fanout_ops_text(body)
        out["max"] = {"ok": True}
    except Exception as exc:  # noqa: BLE001
        logger.warning("site review max notify failed: %s", exc)
        out["max"] = {"ok": False, "error": type(exc).__name__}

    return out


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
def submit_site_review(
    payload: SiteReviewSubmit,
    request: Request,
    x_public_lead_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Поставить цитату в очередь. На рейтинг Яндекса не влияет."""
    if not payload.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="consent_required",
        )
    trusted = _trusted_wp_token(x_public_lead_token)
    if not trusted:
        client_ip = request.client.host if request.client else None
        _require_captcha(
            recaptcha_token=payload.recaptcha_token,
            smartcaptcha_token=payload.smartcaptcha_token,
            client_ip=client_ip,
        )
    source = (payload.source or "site").strip()[:32] or "site"
    result = enqueue_quote(text=payload.text, source=source, consent=True)
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
    item_id = str(result.get("id") or "")
    notify_site_review_queued(
        text=payload.text,
        item_id=item_id,
        source=source,
        send_email=not payload.mail_already_sent,
    )
    return {
        "ok": True,
        "queued": True,
        "id": item_id,
        "detail": "После модерации появится на странице.",
    }
