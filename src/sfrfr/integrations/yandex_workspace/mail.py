"""Исходящая почта через SMTP XOAUTH2 (Яндекс Почта)."""

from __future__ import annotations

import base64
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

from sfrfr.core.config import get_settings
from sfrfr.integrations.yandex_workspace.oauth import token_available, workspace_email


def _xoauth2_plain(user: str, access_token: str) -> str:
    """Незакодированная строка XOAUTH2 (smtplib.auth сам сделает base64)."""
    return f"user={user}\x01auth=Bearer {access_token}\x01\x01"


def _xoauth2_string(user: str, access_token: str) -> str:
    """Base64 для ручного AUTH (тесты / отладка)."""
    return base64.b64encode(_xoauth2_plain(user, access_token).encode("utf-8")).decode("ascii")


_TEMPLATES: dict[str, tuple[str, str]] = {
    "request_docs": (
        "Проверка стажа: нужны документы",
        (
            "Здравствуйте!\n\n"
            "Мы получили вашу заявку на проверку стажа (дело {case_id}).\n"
            "Пожалуйста, загрузите выписку ИЛС (PDF с Госуслуг) и сканы трудовой "
            "в кабинете или мини-приложении MAX — не отвечайте на это письмо вложениями.\n\n"
            "Кабинет: {cabinet_url}\n"
            "С уважением,\nСервис «Проверка стажа»"
        ),
    ),
    "reminder": (
        "Проверка стажа: напоминание",
        (
            "Здравствуйте!\n\n"
            "Напоминаем про дело {case_id}: если документы ещё не загружены — "
            "сделайте это в кабинете ({cabinet_url}) или через MAX.\n\n"
            "С уважением,\nСервис «Проверка стажа»"
        ),
    ),
    "custom": (
        "Проверка стажа",
        "{body}",
    ),
}


def send_mail(
    *,
    to: str,
    template: str = "request_docs",
    case_id: str | None = None,
    subject: str | None = None,
    body: str | None = None,
) -> dict[str, Any]:
    """Отправить письмо. Без СНИЛС/OCR/signed Storage URL в шаблонах."""
    settings = get_settings()
    if not settings.yandex_mail_enabled:
        return {"ok": False, "skipped": True, "reason": "YANDEX_MAIL_ENABLED=false"}
    if not token_available():
        return {"ok": False, "skipped": True, "reason": "no YANDEX_OAUTH_ACCESS_TOKEN"}

    to_addr = (to or "").strip()
    if "@" not in to_addr:
        return {"ok": False, "error": "invalid_to"}

    tpl_key = template if template in _TEMPLATES else "custom"
    tpl_subject, tpl_body = _TEMPLATES[tpl_key]
    cabinet = (settings.cabinet_public_url or "").rstrip("/") + "/"
    fmt = {
        "case_id": (case_id or "—")[:36],
        "cabinet_url": cabinet,
        "body": (body or "").strip() or "Сообщение от сервиса «Проверка стажа».",
    }
    final_subject = (subject or tpl_subject).format(**fmt)[:200]
    final_body = tpl_body.format(**fmt)

    # Защита: не тащим типичные ПДн-маркеры из кастомного body в логи — режем длину
    if any(x in final_body.lower() for x in ("снилс", "snils", "passport", "паспорт")):
        return {"ok": False, "error": "body_contains_forbidden_markers"}

    from_addr = workspace_email()
    token = (settings.yandex_oauth_access_token or "").strip()

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = final_subject
    msg.set_content(final_body)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.yandex.ru", 465, context=context, timeout=30) as smtp:
            smtp.ehlo()
            # smtplib.auth сам base64-кодирует ответ authobject
            smtp.auth("XOAUTH2", lambda _challenge=None: _xoauth2_plain(from_addr, token))
            smtp.send_message(msg)
        return {
            "ok": True,
            "to": to_addr,
            "from": from_addr,
            "template": tpl_key,
            "subject": final_subject,
        }
    except smtplib.SMTPAuthenticationError as exc:
        detail = (
            exc.smtp_error.decode("utf-8", errors="replace")
            if isinstance(exc.smtp_error, bytes)
            else str(exc.smtp_error)
        )[:300]
        hint = None
        low = detail.lower()
        if "access rights" in low or "прав" in low:
            hint = (
                "Включите в настройках Яндекс Почты: «Почтовые клиенты» → IMAP "
                "и «Пароли приложений и OAuth-токены»; в OAuth-приложении — scope mail:smtp"
            )
        return {
            "ok": False,
            "error": "smtp_auth_failed",
            "smtp_code": exc.smtp_code,
            "detail": detail,
            "hint": hint,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}
