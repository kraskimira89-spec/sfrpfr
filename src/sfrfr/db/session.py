from sfrfr.core.config import get_settings


def get_supabase_client():
    """Клиент Supabase (service role для серверной обработки дел)."""
    from supabase import create_client

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Задайте SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY в .env")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
