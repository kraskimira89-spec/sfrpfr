"""Сбор статусов health/ops без ПДн (ТЗ-05)."""

from __future__ import annotations

from typing import Any

from sfrfr.core.config import get_settings


def public_health_payload() -> dict[str, Any]:
    """Публичный /health: без ПДн, без секретов, без содержимого документов."""
    settings = get_settings()
    supabase_configured = bool(settings.supabase_url and settings.supabase_service_role_key)
    max_configured = bool(settings.max_bot_token)
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
        "checks": {
            "supabase_configured": supabase_configured,
            "max_bot_configured": max_configured,
            "webhook_path": "/api/integrations/max/webhook",
            "docs_path": "/docs",
        },
    }


def count_failed_cases() -> int | None:
    """Число дел в pipeline_status=failed. None если БД недоступна."""
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_service_role_key):
        return None
    try:
        from sfrfr.db.session import get_supabase_client

        response = (
            get_supabase_client()
            .table("cases")
            .select("id", count="exact")
            .eq("pipeline_status", "failed")
            .execute()
        )
        if response.count is not None:
            return int(response.count)
        return len(response.data or [])
    except Exception:  # noqa: BLE001 - ops boundary
        return None


def ops_status_payload(*, failed_alert_threshold: int = 1) -> dict[str, Any]:
    """Расширенный статус для мониторинга (без ПДн)."""
    base = public_health_payload()
    settings = get_settings()
    failed = count_failed_cases()
    alert_failed = failed is not None and failed >= failed_alert_threshold
    api_ready = bool(base["checks"]["supabase_configured"])
    return {
        **base,
        "monitor": {
            "api_ready": api_ready,
            "failed_cases": failed,
            "failed_alert": alert_failed,
            "failed_alert_threshold": failed_alert_threshold,
            "max_webhook_url": (
                f"{settings.public_base_url.rstrip('/')}/api/integrations/max/webhook"
            ),
            "public_health_url": f"{settings.public_base_url.rstrip('/')}/health",
            "swagger_url": f"{settings.public_base_url.rstrip('/')}/docs",
        },
    }
