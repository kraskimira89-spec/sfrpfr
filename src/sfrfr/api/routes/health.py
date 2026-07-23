"""Health и ops-мониторинг (ТЗ-05)."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status

from sfrfr.core.config import get_settings
from sfrfr.ops.health import ops_status_payload, public_health_payload

router = APIRouter()


@router.get("/health")
def healthcheck() -> dict:
    """Публичный healthcheck без ПДн. Swagger/браузер без service_role."""
    return public_health_payload()


@router.get("/ops/status")
def ops_status(
    x_ops_token: str | None = Header(default=None, alias="X-Ops-Token"),
) -> dict:
    """
    Мониторинг: failed-дела, готовность API/MAX.
    Доступ по OPS_MONITOR_TOKEN (для cron/alerting), без ПДн в ответе.
    """
    settings = get_settings()
    expected = (settings.ops_monitor_token or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ops monitor token is not configured",
        )
    if not x_ops_token or x_ops_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid ops token")
    return ops_status_payload(failed_alert_threshold=settings.ops_failed_alert_threshold)
