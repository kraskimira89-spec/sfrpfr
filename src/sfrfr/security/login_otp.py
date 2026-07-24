"""Одноразовый код входа через MAX (HMAC-ticket, без отдельной таблицы)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

from sfrfr.core.config import get_settings

_TTL_SECONDS = 10 * 60
_CODE_DIGITS = 6
_SEP = "|"


def _secret() -> bytes:
    settings = get_settings()
    raw = settings.app_secret_key or settings.max_bot_token or "dev-login-otp"
    return raw.encode("utf-8")


def normalize_phone(raw: str) -> str:
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if digits.startswith("7") and len(digits) == 11:
        return "+" + digits
    if raw.strip().startswith("+") and len(digits) >= 10:
        return "+" + digits
    return ("+" + digits) if digits else ""


def _code_hash(code: str, contact: str, max_user_id: str, exp: int) -> str:
    body = f"{code}:{contact}:{max_user_id}:{exp}"
    return hmac.new(_secret(), body.encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class LoginOtpIssue:
    code: str
    ticket: str
    expires_in: int


def issue_login_otp(*, contact: str, max_user_id: str, ttl_seconds: int = _TTL_SECONDS) -> LoginOtpIssue:
    """Сгенерировать код и ticket (в ticket — hash кода, не сам код)."""
    contact_n = contact.strip().lower()
    if not contact_n or not max_user_id:
        raise ValueError("contact and max_user_id required")
    if _SEP in contact_n or _SEP in str(max_user_id):
        raise ValueError("contact/max_user_id must not contain separator")
    code = f"{secrets.randbelow(10**_CODE_DIGITS):0{_CODE_DIGITS}d}"
    exp = int(time.time()) + ttl_seconds
    digest = _code_hash(code, contact_n, str(max_user_id), exp)
    # ticket: contact|max_user_id|exp|digest|sig  (| — чтобы email с точками не ломал разбор)
    body = f"{contact_n}{_SEP}{max_user_id}{_SEP}{exp}{_SEP}{digest}"
    sig = hmac.new(_secret(), body.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return LoginOtpIssue(code=code, ticket=f"{body}{_SEP}{sig}", expires_in=ttl_seconds)


def verify_login_otp(*, ticket: str, code: str) -> tuple[str, str] | None:
    """Вернуть (contact, max_user_id) или None."""
    parts = (ticket or "").strip().split(_SEP)
    if len(parts) != 5:
        return None
    contact, max_user_id, exp_s, digest, sig = parts
    try:
        exp = int(exp_s)
    except ValueError:
        return None
    if exp < int(time.time()):
        return None
    body = f"{contact}{_SEP}{max_user_id}{_SEP}{exp_s}{_SEP}{digest}"
    expected_sig = hmac.new(_secret(), body.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(expected_sig, sig):
        return None
    code_clean = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(code_clean) != _CODE_DIGITS:
        return None
    expected_digest = _code_hash(code_clean, contact, max_user_id, exp)
    if not hmac.compare_digest(expected_digest, digest):
        return None
    return contact, max_user_id
