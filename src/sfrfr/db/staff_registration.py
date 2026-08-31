"""Заявки на доступ в кабинет сотрудника: очередь + одобрение по email."""

from __future__ import annotations

import hashlib
import hmac
import html
import logging
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import quote

from fastapi import HTTPException

from sfrfr.core.config import get_settings
from sfrfr.db.session import get_supabase_client
from sfrfr.db.staff_access import get_staff_row_by_email, invite_staff_member

logger = logging.getLogger(__name__)

_STAFF_REG_NOTIFY_EMAIL = "proverkastaza@yandex.ru"
_SYSTEM_ACTOR_ID = "00000000-0000-0000-0000-000000000000"
StaffRegAction = Literal["approved", "rejected"]


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _moderation_secret() -> str:
    settings = get_settings()
    return (settings.public_lead_token or settings.app_secret_key or "sfrfr").strip()


def staff_reg_sig(request_id: str, action: str) -> str:
    raw = f"staff_reg:{request_id}:{action}".encode()
    return hmac.new(_moderation_secret().encode(), raw, hashlib.sha256).hexdigest()[:32]


def verify_staff_reg_sig(request_id: str, action: str, sig: str) -> bool:
    expected = staff_reg_sig(request_id, action)
    return hmac.compare_digest(expected, (sig or "").strip())


def moderation_urls(request_id: str) -> dict[str, str]:
    base = (get_settings().public_base_url or "https://api.proverkastaza.ru").rstrip("/")
    approved = staff_reg_sig(request_id, "approved")
    rejected = staff_reg_sig(request_id, "rejected")
    return {
        "approved": (
            f"{base}/api/public/staff-register/moderate"
            f"?id={quote(request_id)}&status=approved&sig={approved}"
        ),
        "rejected": (
            f"{base}/api/public/staff-register/moderate"
            f"?id={quote(request_id)}&status=rejected&sig={rejected}"
        ),
    }


def get_request(request_id: str) -> dict[str, Any] | None:
    rows = (
        get_supabase_client()
        .table("staff_registration_requests")
        .select("*")
        .eq("id", request_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def get_pending_by_email(email: str) -> dict[str, Any] | None:
    normalized = email.strip().lower()
    rows = (
        get_supabase_client()
        .table("staff_registration_requests")
        .select("*")
        .eq("status", "pending")
        .ilike("email", normalized)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def create_registration_request(*, email: str, display_name: str) -> dict[str, Any]:
    normalized = email.strip().lower()
    name = display_name.strip()
    if not normalized or "@" not in normalized:
        raise HTTPException(status_code=400, detail="Укажите рабочий e-mail")
    if not name:
        raise HTTPException(status_code=400, detail="Укажите имя и фамилию")

    existing_staff = get_staff_row_by_email(normalized)
    if existing_staff and str(existing_staff.get("status") or "") != "archived":
        raise HTTPException(
            status_code=409,
            detail=(
                "Этот e-mail уже есть в кабинете сотрудников. "
                "Войдите или обратитесь к администратору."
            ),
        )

    if get_pending_by_email(normalized):
        raise HTTPException(
            status_code=409,
            detail=(
                "Заявка с этим e-mail уже на рассмотрении. "
                "Дождитесь ответа администратора."
            ),
        )

    response = (
        get_supabase_client()
        .table("staff_registration_requests")
        .insert(
            {
                "email": normalized,
                "display_name": name,
                "status": "pending",
            }
        )
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=500, detail="Не удалось сохранить заявку")
    row = response.data[0]
    notify_staff_registration_queued(row)
    return {
        "ok": True,
        "id": str(row["id"]),
        "message": (
            "Заявка отправлена. После подтверждения администратором на "
            f"{_STAFF_REG_NOTIFY_EMAIL} вы получите письмо с доступом."
        ),
    }


def notify_staff_registration_queued(row: dict[str, Any]) -> dict[str, Any]:
    request_id = str(row["id"])
    email = str(row.get("email") or "")
    name = str(row.get("display_name") or "")
    urls = moderation_urls(request_id)
    body = (
        "Новая заявка на доступ в кабинет сотрудника\n\n"
        f"Имя: {name}\n"
        f"E-mail: {email}\n"
        f"id: {request_id}\n\n"
        f"Одобрить: {urls['approved']}\n"
        f"Отклонить: {urls['rejected']}\n\n"
        "После одобрения сотруднику уйдёт приглашение на вход."
    )
    html_body = (
        "<p><b>Новая заявка на доступ в кабинет сотрудника</b></p>"
        f"<p><b>Имя:</b> {html.escape(name)}<br>"
        f"<b>E-mail:</b> {html.escape(email)}<br>"
        f"<b>id:</b> <code>{html.escape(request_id)}</code></p>"
        "<p>"
        f'<a href="{html.escape(urls["approved"])}">✅ Одобрить доступ</a>'
        " &nbsp;|&nbsp; "
        f'<a href="{html.escape(urls["rejected"])}">❌ Отклонить</a>'
        "</p>"
        "<p style=\"color:#666;font-size:12px\">"
        "После одобрения сотрудник получит приглашение на e-mail."
        "</p>"
    )
    out: dict[str, Any] = {"email": None}
    try:
        from sfrfr.integrations.yandex_workspace.mail import send_mail

        out["email"] = send_mail(
            to=_STAFF_REG_NOTIFY_EMAIL,
            template="custom",
            subject="[Проверка стажа] Заявка на доступ сотрудника",
            body=body,
            html=html_body,
            from_name="Проверка стажа",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("staff registration email notify failed: %s", exc)
        out["email"] = {"ok": False, "error": type(exc).__name__}
    return out


def moderate_registration_request(
    request_id: str,
    *,
    action: StaffRegAction,
) -> dict[str, Any]:
    row = get_request(request_id)
    if not row:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    current = str(row.get("status") or "")
    if current != "pending":
        return {
            "ok": True,
            "already_reviewed": True,
            "status": current,
            "email": row.get("email"),
            "display_name": row.get("display_name"),
        }

    if action == "rejected":
        (
            get_supabase_client()
            .table("staff_registration_requests")
            .update({"status": "rejected", "reviewed_at": _iso(_now())})
            .eq("id", request_id)
            .execute()
        )
        return {
            "ok": True,
            "status": "rejected",
            "email": row.get("email"),
            "display_name": row.get("display_name"),
        }

    email = str(row.get("email") or "").strip().lower()
    name = str(row.get("display_name") or "").strip()
    invite_staff_member(
        actor_id=_SYSTEM_ACTOR_ID,
        email=email,
        display_name=name,
        role="operator",
    )
    (
        get_supabase_client()
        .table("staff_registration_requests")
        .update({"status": "approved", "reviewed_at": _iso(_now())})
        .eq("id", request_id)
        .execute()
    )
    return {
        "ok": True,
        "status": "approved",
        "email": email,
        "display_name": name,
    }
