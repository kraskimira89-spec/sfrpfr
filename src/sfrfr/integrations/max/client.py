"""Клиент MAX Bot API (отправка сообщений)."""

from __future__ import annotations

from typing import Any

import httpx

from sfrfr.core.config import get_settings


class MaxBotClient:
    """Минимальный HTTP-клиент к platform-api2.max.ru."""

    def __init__(
        self,
        *,
        token: str | None = None,
        api_base: str | None = None,
    ) -> None:
        settings = get_settings()
        self.token = token if token is not None else settings.max_bot_token
        self.api_base = (api_base or settings.max_api_base).rstrip("/")

    @property
    def available(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self.token,
            "Content-Type": "application/json",
        }

    def send_message(self, *, chat_id: int | str, text: str) -> dict[str, Any]:
        """Отправить текст в чат. Без токена — no-op с пометкой."""
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "no MAX_BOT_TOKEN"}
        url = f"{self.api_base}/messages"
        payload = {"chat_id": chat_id, "text": text}
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=self._headers(), json=payload)
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            return data if isinstance(data, dict) else {"raw": data}

    def subscribe_webhook(self, url: str, *, secret: str | None = None) -> dict[str, Any]:
        """POST /subscriptions — зарегистрировать HTTPS webhook."""
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "no MAX_BOT_TOKEN"}
        settings = get_settings()
        body: dict[str, Any] = {"url": url}
        secret_value = secret if secret is not None else settings.max_webhook_secret
        if secret_value:
            body["secret"] = secret_value
        endpoint = f"{self.api_base}/subscriptions"
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(endpoint, headers=self._headers(), json=body)
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            return data if isinstance(data, dict) else {"raw": data}
