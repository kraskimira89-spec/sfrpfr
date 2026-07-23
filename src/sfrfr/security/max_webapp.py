"""Разбор MAX WebApp initData (MVP)."""

from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import parse_qsl


def parse_max_init_data(init_data: str) -> dict[str, str]:
    """Разобрать query-string initData в словарь."""
    return dict(parse_qsl(init_data, keep_blank_values=True))


def extract_max_user_id(init_data: str | None, *, fallback: str | None = None) -> str | None:
    """Достать user.id из initDataUnsafe-совместимой строки или fallback."""
    if init_data and init_data.strip():
        fields = parse_max_init_data(init_data)
        raw_user = fields.get("user")
        if raw_user:
            try:
                user = json.loads(raw_user)
            except json.JSONDecodeError:
                user = None
            if isinstance(user, dict) and user.get("id") is not None:
                return str(user["id"])
        if fields.get("user_id"):
            return str(fields["user_id"])
    if fallback and str(fallback).strip():
        return str(fallback).strip()
    return None


def verify_max_init_data(init_data: str, bot_token: str) -> bool:
    """
    Проверка подписи по схеме, совместимой с Telegram WebApp
    (MAX часто совместим; при иной схеме в проде — донастроить).
    """
    if not init_data or not bot_token:
        return False
    fields = parse_max_init_data(init_data)
    received = fields.pop("hash", None)
    if not received:
        return False
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated = hmac.new(secret, data_check.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calculated, received)
