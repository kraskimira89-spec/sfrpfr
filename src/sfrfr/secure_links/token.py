"""Генерация и хеширование raw-токенов secure action links."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Final

from sfrfr.core.config import Settings, get_settings

# ≥ 32 bytes CSPRNG → token_urlsafe(32) ≈ 256 bit entropy
_TOKEN_BYTES: Final[int] = 32
TOKEN_PREFIX_LEN: Final[int] = 8

PURPOSES: Final[frozenset[str]] = frozenset(
    {
        "consent",
        "upload",
        "view_pdf",
        "pay",
        "diag_share",
    }
)


def generate_raw_token() -> str:
    """Сырой токен для URL; в БД не хранится."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def token_prefix(raw_token: str) -> str:
    """Короткий префикс для логов (не весь секрет)."""
    return (raw_token or "")[:TOKEN_PREFIX_LEN]


def resolve_pepper(settings: Settings | None = None) -> bytes:
    cfg = settings or get_settings()
    raw = (cfg.secure_link_pepper or cfg.app_secret_key or "change-me").strip()
    return raw.encode("utf-8")


def hash_token(
    raw_token: str,
    *,
    pepper: bytes | None = None,
    settings: Settings | None = None,
) -> str:
    """HMAC-SHA256 hex; pepper из SECURE_LINK_PEPPER или APP_SECRET_KEY."""
    key = pepper if pepper is not None else resolve_pepper(settings)
    return hmac.new(key, (raw_token or "").encode("utf-8"), hashlib.sha256).hexdigest()
