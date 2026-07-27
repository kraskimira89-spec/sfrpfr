"""Яндекс Телемост API: создание встречи."""

from __future__ import annotations

from typing import Any

import httpx

from sfrfr.core.config import get_settings
from sfrfr.integrations.yandex_workspace.oauth import oauth_headers, token_available

_TELEMOST_URL = "https://cloud-api.yandex.net/v1/telemost-api/conferences"


def create_conference(
    *,
    waiting_room_level: str = "PUBLIC",
    title_note: str | None = None,
) -> dict[str, Any]:
    """
    Создать видеовстречу. Возвращает join_url при успехе.
    На личном аккаунте без 360 API может ответить 403 ApiRestrictedToOrganizations.
    """
    settings = get_settings()
    if not settings.yandex_telemost_enabled:
        return {"ok": False, "skipped": True, "reason": "YANDEX_TELEMOST_ENABLED=false"}
    if not token_available():
        return {"ok": False, "skipped": True, "reason": "no YANDEX_OAUTH_ACCESS_TOKEN"}

    payload: dict[str, Any] = {"waiting_room_level": waiting_room_level}
    # title_note есть не во всех схемах API; в MVP отправляем пустой body-fields.
    _ = title_note

    try:
        with httpx.Client(timeout=25.0) as client:
            response = client.post(_TELEMOST_URL, headers=oauth_headers(), json=payload)
        body: Any
        try:
            body = response.json() if response.content else {}
        except Exception:  # noqa: BLE001
            body = {"text": (response.text or "")[:300]}

        if response.status_code in (200, 201) and isinstance(body, dict):
            join_url = body.get("join_url") or body.get("joinUrl")
            return {
                "ok": True,
                "status_code": response.status_code,
                "conference_id": body.get("id"),
                "join_url": join_url,
                "response": body,
            }

        err = body.get("error") if isinstance(body, dict) else None
        return {
            "ok": False,
            "status_code": response.status_code,
            "error": err or "telemost_failed",
            "detail": body if isinstance(body, dict) else str(body)[:300],
            "hint": (
                "Нужен Яндекс 360 / scope telemost-api:conferences.create"
                if response.status_code == 403
                else None
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}
