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
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, status

from sfrfr.core.config import get_settings
from sfrfr.integrations.yandex_workspace.mail import send_mail

logger = logging.getLogger(__name__)
router = APIRouter()

_SENDER_NAME = "Проверка стажа. Личный кабинет"
_CABINET = "https://cabinet.proverkastaza.ru/"

_SUBJECTS: dict[str, str] = {
    "signup": "Вход в кабинет «Проверка стажа»",
    "invite": "Приглашение в кабинет «Проверка стажа»",
    "magiclink": "Вход в кабинет «Проверка стажа»",
    "recovery": "Восстановление пароля — «Проверка стажа»",
    "email_change": "Подтвердите новый email — «Проверка стажа»",
    "email": "Вход в кабинет «Проверка стажа»",
    "reauthentication": "Код подтверждения «Проверка стажа»",
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
    raw_meta = user.get("user_metadata")
    meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
    name = str(meta.get("full_name") or "").strip()
    if name:
        return f"Здравствуйте, {escape(name)}!"
    return "Здравствуйте!"


def confirm_url_from_email_data(email_data: dict[str, Any]) -> str:
    """Одноразовая ссылка GoTrue: verify + redirect в кабинет."""
    site = str(email_data.get("site_url") or "").rstrip("/")
    token_hash = str(email_data.get("token_hash") or "").strip()
    action = str(email_data.get("email_action_type") or "magiclink").strip() or "magiclink"
    redirect = str(email_data.get("redirect_to") or _CABINET).strip() or _CABINET
    if not site or not token_hash:
        return ""
    return (
        f"{site}/auth/v1/verify?token={quote(token_hash, safe='')}"
        f"&type={quote(action, safe='')}"
        f"&redirect_to={quote(redirect, safe='')}"
    )


def _build_html(
    *,
    title: str,
    greeting: str,
    lead: str,
    token: str,
    confirm_url: str = "",
) -> str:
    link_block = ""
    if confirm_url:
        link_block = (
            '<p style="margin:0 0 20px;text-align:center;">'
            f'<a href="{escape(confirm_url)}" style="display:inline-block;'
            "padding:14px 22px;background:#1a4d7a;color:#ffffff;text-decoration:none;"
            'border-radius:10px;font-weight:700;font-size:16px;">'
            "Войти в кабинет</a></p>"
            '<p style="margin:0 0 16px;font-size:14px;line-height:1.5;color:#3d4f66;">'
            "Ссылка одноразовая. Откройте её в том же браузере, где начинали регистрацию."
            "</p>"
        )
    token_block = ""
    if token:
        token_label = (
            "Или введите код на странице кабинета:"
            if confirm_url
            else "Введите этот код в личном кабинете на сайте:"
        )
        token_block = (
            f'<p style="margin:0 0 12px;font-size:15px;line-height:1.5;color:#3d4f66;">'
            f"{escape(token_label)}</p>"
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
        link_block,
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


def _compose(
    action: str,
    token: str,
    greeting: str,
    *,
    confirm_url: str = "",
) -> tuple[str, str, str]:
    """subject, plain, html."""
    subject = _SUBJECTS.get(action, _SUBJECTS["magiclink"])
    if "{token}" in subject:
        subject = subject.format(token=token or "")
    greet_plain = greeting.replace("&nbsp;", " ")

    if action in ("signup", "magiclink", "email", "invite"):
        title = "Вход в личный кабинет"
        if confirm_url:
            lead = (
                "Нажмите кнопку ниже — кабинет откроется в браузере. "
                "Если кнопка не открывается, введите код на сайте."
            )
        else:
            lead = "Введите код на сайте кабинета — так мы подтвердим, что это вы."
        plain_parts = [f"{greet_plain}\n"]
        if confirm_url:
            plain_parts.append(f"Войти в кабинет по ссылке:\n{confirm_url}\n")
        if token:
            plain_parts.append(f"Или код для ввода на сайте: {token}\n")
        plain_parts.append(f"\nКабинет: {_CABINET}\n")
        plain = "\n".join(plain_parts)
    elif action == "recovery":
        title = "Восстановление пароля"
        lead = (
            "Мы получили запрос на восстановление пароля. "
            "Откройте ссылку или введите код на сайте."
        )
        plain = (
            f"{greet_plain}\n\n"
            + (f"Ссылка: {confirm_url}\n\n" if confirm_url else "")
            + (f"Код: {token}\n\n" if token else "")
            + f"{_CABINET}\n"
        )
    elif action == "email_change":
        title = "Подтвердите новый email"
        lead = "Чтобы подтвердить новый адрес, откройте ссылку или введите код на сайте."
        plain = (
            f"{greet_plain}\n\n"
            + (f"Ссылка: {confirm_url}\n" if confirm_url else "")
            + (f"Код: {token}\n" if token else "")
        )
    else:
        title = "Код подтверждения"
        lead = "Ваш код подтверждения:"
        plain = f"{greet_plain}\n\nКод подтверждения: {token}\n"

    html = _build_html(
        title=title,
        greeting=greeting,
        lead=lead,
        token=token,
        confirm_url=confirm_url,
    )
    return subject, plain, html


@router.post("/auth-send-email")
async def supabase_auth_send_email(request: Request) -> dict[str, Any]:
    """
    HTTPS Auth Hook (Send Email): письмо уходит с Яндекс-ящика РФ,
    отправитель — «Проверка стажа. Личный кабинет».
    """
    # #region agent log
    def _dbg(message: str, hypothesis_id: str, data: dict[str, Any]) -> None:
        try:
            from sfrfr.api.routes.public_debug_session import _write_ndjson

            _write_ndjson(
                {
                    "sessionId": "d43d44",
                    "location": "supabase_auth_email.py:auth-send-email",
                    "message": message,
                    "hypothesisId": hypothesis_id,
                    "data": data,
                    "timestamp": int(time.time() * 1000),
                    "runId": "pre",
                    "source": "hook",
                }
            )
        except Exception:  # noqa: BLE001
            pass
        logger.warning("DEBUG-d43d44 %s %s %s", hypothesis_id, message, data)

    # #endregion

    settings = get_settings()
    secret = (settings.supabase_send_email_hook_secret or "").strip()
    # #region agent log
    _dbg(
        "hook_entered",
        "A",
        {"secret_configured": bool(secret), "body_len": 0},
    )
    # #endregion
    if not secret:
        # #region agent log
        _dbg("hook_not_configured", "C", {})
        # #endregion
        raise HTTPException(status_code=503, detail="hook_not_configured")

    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    # #region agent log
    _dbg(
        "hook_headers",
        "C",
        {
            "body_len": len(body),
            "has_webhook_id": bool(headers.get("webhook-id")),
            "has_webhook_signature": bool(headers.get("webhook-signature")),
            "has_webhook_timestamp": bool(headers.get("webhook-timestamp")),
        },
    )
    # #endregion
    try:
        _verify_standard_webhook(body=body, headers=headers, secret_raw=secret)
    except HTTPException as exc:
        # #region agent log
        _dbg("hook_signature_failed", "C", {"status": exc.status_code, "detail": str(exc.detail)})
        # #endregion
        raise

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid_json") from exc

    user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    email_data = payload.get("email_data") if isinstance(payload.get("email_data"), dict) else {}
    to_addr = str(user.get("email") or "").strip()
    if not to_addr or "@" not in to_addr:
        # #region agent log
        _dbg("missing_email", "D", {"has_user": bool(user)})
        # #endregion
        raise HTTPException(status_code=400, detail="missing_email")

    action = str(email_data.get("email_action_type") or "magiclink").strip().lower()
    token = str(email_data.get("token") or "").strip()
    confirm_url = confirm_url_from_email_data(email_data)
    greeting = _greeting(user)
    subject, plain, html = _compose(
        action,
        token,
        greeting,
        confirm_url=confirm_url,
    )
    # #region agent log
    _dbg(
        "hook_payload_ready",
        "D",
        {
            "action": action,
            "has_token": bool(token),
            "token_len": len(token),
            "has_confirm_url": bool(confirm_url),
            "has_token_hash": bool(str(email_data.get("token_hash") or "").strip()),
            "email_domain": to_addr.split("@")[-1].lower() if "@" in to_addr else "",
        },
    )
    # #endregion
    if not token and not confirm_url:
        logger.warning("auth send-email: empty token and confirm_url action=%s", action)
        # #region agent log
        _dbg("missing_token", "D", {"action": action})
        # #endregion
        raise HTTPException(status_code=400, detail="missing_token")

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
        # #region agent log
        _dbg(
            "smtp_failed",
            "D",
            {
                "error": str(result.get("error") or result.get("reason") or "send_failed")[:120],
            },
        )
        # #endregion
        raise HTTPException(
            status_code=502,
            detail={
                "error": {
                    "http_code": 502,
                    "message": str(result.get("error") or result.get("reason") or "send_failed"),
                }
            },
        )
    # #region agent log
    _dbg("smtp_ok", "D", {"action": action, "has_confirm_url": bool(confirm_url)})
    # #endregion
    return {}
