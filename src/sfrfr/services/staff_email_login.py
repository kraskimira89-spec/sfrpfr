"""Precheck входа сотрудника по e-mail OTP + уведомление администратора."""

from __future__ import annotations

import html
import logging
from typing import Any

from sfrfr.db.session import get_supabase_client
from sfrfr.db.staff_roles import _staff_row_by_email, get_staff_role_by_email

logger = logging.getLogger(__name__)

_STAFF_LOGIN_NOTIFY_EMAIL = "proverkastaza@yandex.ru"
_ADMIN_CABINET_URL = "https://admin.proverkastaza.ru/"

_REASON_LABELS: dict[str, str] = {
    "no_staff_role": "нет назначенной роли сотрудника",
    "no_auth_user": "нет учётной записи для входа (нужно приглашение администратора)",
}


def _user_email(user: Any) -> str | None:
    return getattr(user, "email", None) or (user.get("email") if isinstance(user, dict) else None)


def _auth_user_ready(email: str) -> bool:
    normalized = email.strip().lower()
    row = _staff_row_by_email(normalized)
    if row and row.get("user_id"):
        try:
            get_supabase_client().auth.admin.get_user_by_id(str(row["user_id"]))
            return True
        except Exception:  # noqa: BLE001
            pass
    try:
        link = get_supabase_client().auth.admin.generate_link(
            {"type": "magiclink", "email": normalized}
        )
        user = getattr(link, "user", None)
        if user is None:
            return False
        return (_user_email(user) or "").strip().lower() == normalized
    except Exception:  # noqa: BLE001
        return False


def staff_email_login_allowed(email: str) -> tuple[bool, str]:
    """Можно ли отправлять OTP на этот адрес сотрудника."""
    normalized = email.strip().lower()
    if not normalized or "@" not in normalized:
        return False, "invalid_email"
    if get_staff_role_by_email(normalized) is None:
        return False, "no_staff_role"
    if not _auth_user_ready(normalized):
        return False, "no_auth_user"
    return True, "ok"


def notify_staff_login_blocked(*, email: str, reason: str) -> dict[str, Any]:
    """Сообщить администратору о попытке входа с неподготовленной почтой."""
    normalized = email.strip().lower()
    reason_label = _REASON_LABELS.get(reason, reason)
    body = (
        "Попытка входа в кабинет сотрудника по рабочей почте.\n\n"
        f"E-mail: {normalized}\n"
        f"Причина блокировки: {reason_label}\n\n"
        f"Кабинет: {_ADMIN_CABINET_URL}\n"
        "Действия администратора:\n"
        f"• пригласить: sfrfr staff-grant --email {normalized} "
        "--role operator --invite\n"
        "• или одобрить заявку на доступ, если она уже есть.\n"
    )
    html_body = (
        "<p><b>Попытка входа в кабинет сотрудника</b></p>"
        f"<p><b>E-mail:</b> {html.escape(normalized)}<br>"
        f"<b>Причина:</b> {html.escape(reason_label)}</p>"
        f'<p><a href="{html.escape(_ADMIN_CABINET_URL)}">Открыть кабинет сотрудника</a></p>'
        "<p style=\"color:#666;font-size:12px\">"
        "После назначения роли и учётной записи сотрудник сможет получить код на почту."
        "</p>"
    )
    out: dict[str, Any] = {"email": None}
    try:
        from sfrfr.integrations.yandex_workspace.mail import send_mail

        out["email"] = send_mail(
            to=_STAFF_LOGIN_NOTIFY_EMAIL,
            template="custom",
            subject="[Проверка стажа] Запрос входа сотрудника",
            body=body,
            html=html_body,
            from_name="Проверка стажа",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("staff login blocked notify failed: %s", exc)
        out["email"] = {"ok": False, "error": type(exc).__name__}
    return out


def prepare_staff_email_otp(email: str) -> dict[str, Any]:
    """Precheck перед signInWithOtp в admin: allowed + текст для UI."""
    normalized = email.strip().lower()
    allowed, reason = staff_email_login_allowed(normalized)
    if allowed:
        return {
            "ok": True,
            "allowed": True,
            "message": "Код можно отправить на рабочую почту.",
        }
    notify_staff_login_blocked(email=normalized, reason=reason)
    return {
        "ok": True,
        "allowed": False,
        "reason": reason,
        "message": (
            "Этот адрес не зарегистрирован для входа в кабинет сотрудника. "
            "Обратитесь к администратору — мы отправили запрос на "
            f"{_STAFF_LOGIN_NOTIFY_EMAIL}."
        ),
    }
