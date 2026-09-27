import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from postgrest.constants import DEFAULT_POSTGREST_CLIENT_TIMEOUT

from sfrfr.core.config import get_settings


def _import_from_supabase(name: str) -> Any:
    """Импорт из supabase без конфликта с локальной папкой ./supabase (migrations)."""
    cwd = str(Path.cwd().resolve())
    removed: list[str] = []
    for entry in ("", cwd):
        while entry in sys.path:
            sys.path.remove(entry)
            removed.append(entry)
    try:
        import supabase as sb

        return getattr(sb, name)
    finally:
        for entry in reversed(removed):
            sys.path.insert(0, entry)


@lru_cache
def _client_factory():
    return _import_from_supabase("create_client")


def supabase_client_options():
    """ClientOptions с httpx: без deprecated timeout/verify у SyncPostgrestClient."""
    client_options = _import_from_supabase("ClientOptions")
    return client_options(
        httpx_client=httpx.Client(
            timeout=httpx.Timeout(DEFAULT_POSTGREST_CLIENT_TIMEOUT),
            verify=True,
        )
    )


def get_supabase_client():
    """Клиент Supabase (service role для серверной обработки дел)."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Задайте SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY в .env")
    return _client_factory()(
        settings.supabase_url,
        settings.supabase_service_role_key,
        options=supabase_client_options(),
    )


def get_supabase_user_client():
    """Клиент с publishable/anon key: только для проверки пользовательского JWT."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise RuntimeError("Задайте SUPABASE_URL и SUPABASE_ANON_KEY в .env")
    return _client_factory()(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=supabase_client_options(),
    )
