"""CTA-ссылки уведомлений с учётом preferred_channel (ТЗ-09)."""

from __future__ import annotations

from typing import Any

from sfrfr.core.config import get_settings


def notification_channel_links(
    *,
    preferred_channel: str | None,
    max_linked: bool,
    case_id: str | None = None,
) -> dict[str, Any]:
    """
    Две ссылки (кабинет + MAX); порядок по предпочтению канала.
    Не блокирует другой канал — только порядок CTA.
    """
    settings = get_settings()
    cabinet = settings.cabinet_public_url.rstrip("/")
    if case_id:
        cabinet = f"{cabinet}/?case={case_id}"
    else:
        cabinet = f"{cabinet}/"

    max_url = settings.max_public_bot_url
    miniapp = settings.max_miniapp_url.rstrip("/") + "/"

    links = [
        {
            "channel": "web_cabinet",
            "label": "Веб-кабинет",
            "url": cabinet,
            "copy": "В браузере — удобнее с компьютера и большим экраном",
        },
        {
            "channel": "max_miniapp",
            "label": "Мини-приложение MAX",
            "url": miniapp if max_linked else max_url,
            "copy": "В MAX — быстро из мессенджера",
            "bot_url": max_url,
        },
    ]
    preferred = preferred_channel or "unset"
    if preferred == "max_miniapp":
        links = list(reversed(links))
    return {
        "preferred_channel": preferred,
        "links": links,
        "note": "Оба варианта: одни и те же документы и статус дела",
        "warning": "Решение принимает СФР. Результат не гарантирован.",
    }
