"""Клиент к локальному PostgREST :55433 с API `.table()`, как у supabase.

Приложение ходит в `{SUPABASE_URL}/rest/v1`. Локальный PostgREST слушает `/`.
Поэтому здесь SyncPostgrestClient напрямую (тот же HTTP/CAS), без cloud Auth.
"""

from __future__ import annotations

import os
from typing import Any

import jwt
from postgrest import SyncPostgrestClient

DEFAULT_JWT_SECRET = "precheck-e2e-jwt-secret-local-only-not-prod"
DEFAULT_REST_URL = "http://127.0.0.1:55433"


def mint_precheck_service_jwt(
    *,
    secret: str | None = None,
    role: str = "sfrfr",
) -> str:
    sec = (
        secret
        or os.environ.get("PRECHECK_POSTGREST_JWT_SECRET")
        or DEFAULT_JWT_SECRET
    ).strip()
    return jwt.encode({"role": role}, sec, algorithm="HS256")


class AppLikePostgrestClient:
    """Обёртка: `.table(name)` → PostgREST `.from_(name)`."""

    def __init__(self, rest: SyncPostgrestClient) -> None:
        self._rest = rest

    def table(self, name: str) -> Any:
        return self._rest.from_(name)


def build_precheck_supabase_client() -> AppLikePostgrestClient:
    url = (os.environ.get("PRECHECK_POSTGREST_URL") or DEFAULT_REST_URL).rstrip("/")
    key = mint_precheck_service_jwt()
    rest = SyncPostgrestClient(
        url,
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    return AppLikePostgrestClient(rest)


def postgrest_reachable(timeout: float = 2.0) -> bool:
    import urllib.request

    url = (os.environ.get("PRECHECK_POSTGREST_URL") or DEFAULT_REST_URL).rstrip("/") + "/"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return int(resp.status) < 500
    except Exception:  # noqa: BLE001
        return False
