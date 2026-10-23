"""Канонические URL возврата после оплаты ЮKassa (без legacy taxi-домена)."""

from __future__ import annotations

from typing import Literal

from sfrfr.core.config import get_settings

ReturnChannel = Literal["web_cabinet", "max_miniapp"]

_LEGACY_TAXI_HOST = "taxi-doroga-dobra.ru"
_CANON_SITE = "https://proverkastaza.ru"
_CANON_CABINET = "https://cabinet.proverkastaza.ru"
_CANON_API = "https://api.proverkastaza.ru"
_CANON_ADMIN = "https://admin.proverkastaza.ru"


def canon_public_url(url: str) -> str:
    """Убрать legacy taxi-домен из return/base URL (канон — proverkastaza.ru)."""
    raw = (url or "").strip()
    if not raw:
        return raw
    if _LEGACY_TAXI_HOST not in raw.lower():
        return raw
    lowered = raw.lower()
    if "cabinet." in lowered:
        return _CANON_CABINET
    if "api." in lowered:
        return _CANON_API
    if "admin." in lowered:
        return _CANON_ADMIN
    return _CANON_SITE


def payment_return_url(case_id: str, channel: ReturnChannel = "web_cabinet") -> str:
    settings = get_settings()
    if settings.yookassa_return_url:
        base = canon_public_url(settings.yookassa_return_url).rstrip("/")
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}case={case_id}&view=payments&paid=1"
    if channel == "max_miniapp":
        mini = canon_public_url(settings.max_miniapp_url).rstrip("/") + "/"
        return f"{mini}?case={case_id}&view=payments&paid=1"
    cabinet = canon_public_url(settings.cabinet_public_url).rstrip("/")
    return f"{cabinet}/cases/{case_id}?view=payments&paid=1"
