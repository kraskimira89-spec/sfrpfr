"""HMAC one-time token для связки MAX → веб-кабинет (без initData в кабинете)."""

from __future__ import annotations

import hashlib
import hmac
import time

from sfrfr.core.config import get_settings

_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 дней


def _secret() -> bytes:
    settings = get_settings()
    raw = settings.app_secret_key or settings.max_bot_token or "dev-link-secret"
    return raw.encode("utf-8")


def make_max_link_token(max_user_id: str, *, ttl_seconds: int = _TTL_SECONDS) -> str:
    """Подписанный токен: max_user_id.exp.sig"""
    exp = int(time.time()) + ttl_seconds
    body = f"{max_user_id}.{exp}"
    sig = hmac.new(_secret(), body.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{sig}"


def verify_max_link_token(token: str) -> str | None:
    """Вернуть max_user_id или None."""
    parts = (token or "").strip().split(".")
    if len(parts) != 3:
        return None
    max_user_id, exp_s, sig = parts
    try:
        exp = int(exp_s)
    except ValueError:
        return None
    if exp < int(time.time()):
        return None
    body = f"{max_user_id}.{exp_s}"
    expected = hmac.new(_secret(), body.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(expected, sig):
        return None
    if not max_user_id:
        return None
    return max_user_id
