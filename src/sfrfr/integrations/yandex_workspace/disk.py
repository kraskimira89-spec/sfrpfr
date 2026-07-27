"""Яндекс Диск — выключен по умолчанию (ПДн → Supabase Storage)."""

from __future__ import annotations

from typing import Any

from sfrfr.core.config import get_settings


def disk_status() -> dict[str, Any]:
    settings = get_settings()
    if not settings.yandex_disk_enabled:
        return {
            "ok": False,
            "skipped": True,
            "reason": "YANDEX_DISK_ENABLED=false",
            "policy": "ПДн-сканы только в Supabase Storage (ТЗ-14)",
        }
    return {"ok": False, "skipped": True, "reason": "disk_api_not_implemented"}
