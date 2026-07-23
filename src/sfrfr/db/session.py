import sys
from functools import lru_cache
from pathlib import Path

from sfrfr.core.config import get_settings


def _create_client_fn():
    """Импорт create_client без конфликта с локальной папкой ./supabase (migrations)."""
    cwd = str(Path.cwd().resolve())
    removed: list[str] = []
    for entry in ("", cwd):
        while entry in sys.path:
            sys.path.remove(entry)
            removed.append(entry)
    try:
        from supabase import create_client
    finally:
        for entry in reversed(removed):
            sys.path.insert(0, entry)
    return create_client


@lru_cache
def _client_factory():
    return _create_client_fn()


def get_supabase_client():
    """Клиент Supabase (service role для серверной обработки дел)."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Задайте SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY в .env")
    return _client_factory()(settings.supabase_url, settings.supabase_service_role_key)


def get_supabase_user_client():
    """Клиент с publishable/anon key: только для проверки пользовательского JWT."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise RuntimeError("Задайте SUPABASE_URL и SUPABASE_ANON_KEY в .env")
    return _client_factory()(settings.supabase_url, settings.supabase_anon_key)
