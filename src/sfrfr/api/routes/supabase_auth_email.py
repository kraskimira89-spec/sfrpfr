"""Supabase Auth Send Email Hook → исходящая почта Яндекс (РФ)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from html import escape
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from sfrfr.core.config import get_settings
from sfrfr.integrations.yandex_workspace.mail import send_mail

logger = logging.getLogger(__name__)
router = APIRouter()

_SENDER_NAME = "Проверка стажа. Личный кабинет"
_CABINET = "https://cabinet.proverkastaza.ru/"

_SUBJECTS: dict[str, str] = {
    "signup": "Код для кабинета «Проверка стажа»: {token}",
    "invite": "Приглашение в кабинет «Проверка стажа»",
    "magiclink": "Код для входа в «Проверка стажа»: {token}",
    "recovery": "Восстановление пароля — «Проверка стажа»",
    "email_change": "Подтвердите новый email — «Проверка стажа»",
    "email": "Код для кабинета «Проверка стажа»: {token}",
    "reauthentication": "{token} — код подтверждения «Проверка стажа»",
}


def _hook_secret_bytes(raw: str) -> bytes:
    """Из `v1,whsec_<base64>` получить ключ для HMAC."""
    secret = (raw or "").strip()
    if secret.startswith("v1,"):
        secret = secret[3:]
    if secret.startswith("whsec_"):
        secret = secret[len("whsec_") :]
    try:
        return base64.b64decode(secret)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="invalid_hook_secret",
        ) from exc


def _verify_standard_webhook(*, body: bytes, headers: dict[str, str], secret_raw: str) -> None:
    msg_id = headers.get("webhook-id") or ""
    ts = headers.get("webhook-timestamp") or ""
    sig_header = headers.get("webhook-signature") or ""
    if not msg_id or not ts or not sig_header:
        raise HTTPException(status_code=401, detail="missing_webhook_headers")
    try:
        ts_i = int(ts)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="bad_timestamp") from exc
    if abs(int(time.time()) - ts_i) > 300:
        raise HTTPException(status_code=401, detail="timestamp_out_of_range")

    signed = f"{msg_id}.{ts}.".encode() + body
    key = _hook_secret_bytes(secret_raw)
    digest = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode("ascii")
    expected = {part.strip().split(",", 1)[-1] for part in sig_header.split(" ") if part.strip()}
    if digest not in expected:
        raise HTTPException(status_code=401, detail="invalid_signature")


def _greeting(user: dict[str, Any]) -> str:
    meta = user.get("user_metadata") if isinstance(user.get("user_metadata"), dict) else {}
    name = str(meta.get("full_name") or "").strip()
    if name:
        return f"Здравствуйте, {escape(name)}!"
    return "Здравствуйте!"


def _build_html(*, title: str, greeting: str, lead: str, token: str) -> str:
    token_block = ""
    if token:
        token_block = (
            "<p style=\"margin:0 0 20px;text-align:center;font-size:32px;"
            "letter-spacing:0.28em;font-weight:700;"
            f"font-variant-numeric:tabular-nums;\">{escape(token)}</p>"
        )
    # HTML-шаблон в списке строк — иначе ruff E501 на длинных style=
    parts = [
        "<!DOCTYPE html>",
        '<html lang="ru">',
        "<body style=\"margin:0;padding:0;background:#f3f6fa;",
        "font-family:'Segoe UI',Arial,sans-serif;color:#122033;\">",
        '<table role="presentation" width="100%" cellspacing="0"',
        ' cellpadding="0" style="background:#f3f6fa;padding:24px 12px;">',
        "<tr><td align=\"center\">",
        '<table role="presentation" width="100%" cellspacing="0"',
        ' cellpadding="0" style="max-width:560px;background:#ffffff;',
        "border:1px solid #c9d6e5;border-radius:12px;padding:28px 24px;\">",
        "<tr><td>",
        '<p style="margin:0 0 8px;font-size:14px;font-weight:700;',
        'color:#1a4d7a;">Проверка стажа</p>',
        f'<h1 style="margin:0 0 16px;font-size:22px;line-height:1.3;">'
        f"{escape(title)}</h1>",
        f'<p style="margin:0 0 12px;font-size:16px;line-height:1.5;">{greeting}</p>',
        '<p style="margin:0 0 16px;font-size:16px;line-height:1.5;',
        f'color:#3d4f66;">{escape(lead)}</p>',
        token_block,
        '<p style="margin:0;font-size:14px;line-height:1.5;color:#3d4f66;">',
        f'Кабинет: <a href="{_CABINET}" style="color:#1a4d7a;">{_CABINET}</a>',
        "</p>",
        "</td></tr></table>",
        '<p style="margin:16px 0 0;font-size:12px;color:#3d4f66;">',
        "proverkastaza.ru · личный кабинет</p>",
        "</td></tr></table>",
        "</body></html>",
    ]
    return "".join(parts)


def _compose(action: str, token: str, greeting: str) -> tuple[str, str, str]:
    """subject, plain, html."""
    subject_tpl = _SUBJECTS.get(action, _SUBJECTS["magiclink"])
    subject = subject_tpl.format(token=token)
    greet_plain = greeting.replace("&nbsp;", " ")

    if action in ("signup", "magiclink", "email", "invite"):
        title = "Код для входа в кабинет"
        lead = "Введите этот код в личном кабинете на сайте — так мы подтвердим, что это вы:"
        plain = (
            f"{greet_plain}\n\n"
            f"Ваш код для входа в личный кабинет «Проверка стажа»: {token}\n\n"
            f"Введите код на сайте {_CABINET}\n"
        )
    elif action == "recovery":
        title = "Восстановление пароля"
        lead = "Мы получили запрос на восстановление пароля. Введите код на сайте:"
        plain = (
            f"{greet_plain}\n\n"
            f"Код для восстановления пароля в кабинете «Проверка стажа»: {token}\n\n"
            f"{_CABINET}\n"
        )
    elif action == "email_change":
        title = "Подтвердите новый email"
        lead = "Чтобы подтвердить новый адрес, введите код на сайте:"
        plain = f"{greet_plain}\n\nКод подтверждения нового email: {token}\n"
    else:
        title = "Код подтверждения"
        lead = "Ваш код подтверждения:"
        plain = f"{greet_plain}\n\nКод подтверждения: {token}\n"

    html = _build_html(title=title, greeting=greeting, lead=lead, token=token)
    return subject, plain, html


@router.post("/auth-send-email")
async def supabase_auth_send_email(request: Request) -> dict[str, Any]:
    """
    HTTPS Auth Hook (Send Email): письмо уходит с Яндекс-ящика РФ,
    отправитель — «Проверка стажа. Личный кабинет».
    """
    settings = get_settings()
    secret = (settings.supabase_send_email_hook_secret or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="hook_not_configured")

    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    _verify_standard_webhook(body=body, headers=headers, secret_raw=secret)

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid_json") from exc

    user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    email_data = payload.get("email_data") if isinstance(payload.get("email_data"), dict) else {}
    to_addr = str(user.get("email") or "").strip()
    if not to_addr or "@" not in to_addr:
        raise HTTPException(status_code=400, detail="missing_email")

    action = str(email_data.get("email_action_type") or "magiclink").strip().lower()
    token = str(email_data.get("token") or "").strip()
    greeting = _greeting(user)
    subject, plain, html = _compose(action, token, greeting)

    result = send_mail(
        to=to_addr,
        template="custom",
        subject=subject,
        body=plain,
        html=html,
        from_name=_SENDER_NAME,
    )
    if not result.get("ok"):
        logger.warning("auth send-email hook failed: %s", result)
        raise HTTPException(
            status_code=502,
            detail={
                "error": {
                    "http_code": 502,
                    "message": str(result.get("error") or result.get("reason") or "send_failed"),
                }
            },
        )
    return {}
