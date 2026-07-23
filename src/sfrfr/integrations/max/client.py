"""Клиент MAX Bot API (отправка сообщений)."""

from __future__ import annotations

from typing import Any

import httpx

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.ssl_context import max_ssl_verify


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

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=30.0, verify=max_ssl_verify())

    def send_message(
        self,
        *,
        text: str,
        user_id: int | str | None = None,
        chat_id: int | str | None = None,
    ) -> dict[str, Any]:
        """Отправить текст. Личный диалог — user_id, группа — chat_id (query)."""
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "no MAX_BOT_TOKEN"}
        if user_id is None and chat_id is None:
            return {"ok": False, "skipped": True, "reason": "no recipient"}
        url = f"{self.api_base}/messages"
        # Личный диалог в MAX адресуется user_id; chat_id — для групп/каналов.
        params: dict[str, int | str] = {}
        if user_id is not None:
            params["user_id"] = user_id
        elif chat_id is not None:
            params["chat_id"] = chat_id
        payload = {"text": text}
        with self._client() as client:
            resp = client.post(url, headers=self._headers(), params=params, json=payload)
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            return data if isinstance(data, dict) else {"raw": data}

    def subscribe_webhook(self, url: str, *, secret: str | None = None) -> dict[str, Any]:
        """POST /subscriptions — зарегистрировать HTTPS webhook."""
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "no MAX_BOT_TOKEN"}
        settings = get_settings()
        body: dict[str, Any] = {
            "url": url,
            "update_types": ["message_created", "bot_started"],
        }
        secret_value = secret if secret is not None else settings.max_webhook_secret
        if secret_value:
            body["secret"] = secret_value
        endpoint = f"{self.api_base}/subscriptions"
        with self._client() as client:
            resp = client.post(endpoint, headers=self._headers(), json=body)
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            return data if isinstance(data, dict) else {"raw": data}
