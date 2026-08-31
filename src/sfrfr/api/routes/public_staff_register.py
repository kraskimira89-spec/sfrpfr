"""Публичная заявка на доступ в кабинет сотрудника + модерация по email."""

from __future__ import annotations

import html

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from sfrfr.db.staff_registration import (
    create_registration_request,
    moderate_registration_request,
    verify_staff_reg_sig,
)

router = APIRouter()

_ADMIN_CABINET_URL = "https://admin.proverkastaza.ru/"


class StaffRegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=2, max_length=120)
    consent: bool = Field(description="Согласие на обработку ПДн для рассмотрения заявки")


@router.post("/staff-register")
def submit_staff_register(payload: StaffRegisterRequest) -> dict:
    if not payload.consent:
        raise HTTPException(status_code=400, detail="consent_required")
    return create_registration_request(
        email=payload.email,
        display_name=payload.display_name,
    )


@router.get("/staff-register/moderate", response_class=HTMLResponse)
def moderate_staff_register_link(
    id: str,
    status: str,
    sig: str,
) -> HTMLResponse:
    request_id = (id or "").strip()
    review_status = (status or "").strip().lower()
    if review_status not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="bad_status")
    if not request_id or not verify_staff_reg_sig(request_id, review_status, sig):
        raise HTTPException(status_code=403, detail="bad_signature")

    try:
        result = moderate_registration_request(
            request_id,
            action=review_status,  # type: ignore[arg-type]
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        return _moderation_result_page(
            request_id=request_id,
            review_status=review_status,
            email="",
            display_name="",
            error=str(exc)[:200],
        )

    return _moderation_result_page(
        request_id=request_id,
        review_status=str(result.get("status") or review_status),
        email=str(result.get("email") or ""),
        display_name=str(result.get("display_name") or ""),
        already_reviewed=bool(result.get("already_reviewed")),
    )


def _moderation_result_page(
    *,
    request_id: str,
    review_status: str,
    email: str,
    display_name: str,
    error: str | None = None,
    already_reviewed: bool = False,
) -> HTMLResponse:
    if error:
        headline = "Не удалось обработать заявку"
    elif review_status == "approved":
        headline = (
            "Доступ одобрен. Сотруднику отправлено приглашение на e-mail."
            if not already_reviewed
            else "Заявка уже была одобрана ранее."
        )
    else:
        headline = (
            "Заявка отклонена."
            if not already_reviewed
            else "Заявка уже была отклонена ранее."
        )

    details = ""
    if email.strip():
        details = (
            f"<p><b>Имя:</b> {html.escape(display_name)}<br>"
            f"<b>E-mail:</b> {html.escape(email)}</p>"
        )
    err_html = (
        f"<p style=\"color:#b45309\">{html.escape(error)}</p>" if error else ""
    )
    page = (
        "<!doctype html><html lang=\"ru\"><meta charset=\"utf-8\">"
        "<title>Заявка сотрудника</title>"
        "<body style=\"font-family:sans-serif;max-width:32rem;margin:2rem auto;padding:0 1rem\">"
        f"<h1>{html.escape(headline)}</h1>"
        f"{err_html}"
        f"{details}"
        f"<p><a href=\"{html.escape(_ADMIN_CABINET_URL)}\">Кабинет сотрудника</a></p>"
        f"<p style=\"color:#666;font-size:12px\">id: <code>{html.escape(request_id)}</code></p>"
        "</body></html>"
    )
    return HTMLResponse(page)
