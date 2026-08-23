"""Клиент MAX Bot API (отправка сообщений)."""

from __future__ import annotations

from typing import Any

import httpx

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.ssl_context import max_ssl_verify


def inline_callback_keyboard(text: str, payload: str) -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [[{"type": "callback", "text": text, "payload": payload}]]
    )


def inline_get_login_code_keyboard() -> list[dict[str, Any]]:
    """Кнопка «Получить код для входа» в чате MAX."""
    from sfrfr.security.login_otp import GET_CODE_CALLBACK, GET_CODE_IN_BROWSER_LABEL

    return inline_callback_keyboard(GET_CODE_IN_BROWSER_LABEL, GET_CODE_CALLBACK)


def inline_buttons_keyboard(rows: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Произвольная inline-клавиатура (callback / link)."""
    return [
        {
            "type": "inline_keyboard",
            "payload": {"buttons": rows},
        }
    ]


def inline_link_keyboard(text: str, url: str) -> list[dict[str, Any]]:
    return inline_buttons_keyboard([[{"type": "link", "text": text, "url": url}]])


def inline_channel_choice_keyboard(*, app_url: str, cabinet_url: str) -> list[dict[str, Any]]:
    """Две ссылки после входа: приложение MAX и веб-интерфейс."""
    from sfrfr.security.login_otp import WORK_IN_APP_LABEL, WORK_IN_INTERFACE_LABEL

    return [
        {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [{"type": "link", "text": WORK_IN_APP_LABEL, "url": app_url}],
                    [{"type": "link", "text": WORK_IN_INTERFACE_LABEL, "url": cabinet_url}],
                ],
            },
        }
    ]


def inline_confirm_login_keyboard(
    *,
    ticket_id: str,
    login_url: str | None = None,
    label: str | None = None,
) -> list[dict[str, Any]]:
    """Callback (всегда видна) + опционально link (открывает браузер)."""
    from sfrfr.security.login_otp import CONFIRM_WEB_LOGIN_LABEL, OPEN_CABINET_BUTTON_LABEL

    button_label = label or CONFIRM_WEB_LOGIN_LABEL
    rows: list[list[dict[str, Any]]] = [
        [
            {
                "type": "callback",
                "text": button_label,
                "payload": f"confirm_web_login|{ticket_id}",
            }
        ]
    ]
    if login_url:
        rows.append(
            [{"type": "link", "text": OPEN_CABINET_BUTTON_LABEL, "url": login_url}]
        )
    return [
        {
            "type": "inline_keyboard",
            "payload": {"buttons": rows},
        }
    ]


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

    @classmethod
    def for_ops(cls) -> MaxBotClient:
        """Клиент ops-бота (ТЗ-25); без MAX_OPS_BOT_TOKEN — клиентский токен."""
        settings = get_settings()
        ops = (settings.max_ops_bot_token or "").strip()
        if ops:
            return cls(token=ops)
        return cls()

    @property
    def available(self) -> bool:
        return bool(self.token)

    @property
    def uses_ops_token(self) -> bool:
        settings = get_settings()
        ops = (settings.max_ops_bot_token or "").strip()
        return bool(ops) and self.token == ops

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
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Отправить текст. Личный диалог — user_id, группа — chat_id (query)."""
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "no MAX_BOT_TOKEN"}
        if user_id is None and chat_id is None:
            return {"ok": False, "skipped": True, "reason": "no recipient"}
        url = f"{self.api_base}/messages"
        params: dict[str, int | str] = {}
        if user_id is not None:
            params["user_id"] = user_id
        elif chat_id is not None:
            params["chat_id"] = chat_id
        payload: dict[str, Any] = {"text": text}
        if attachments:
            payload["attachments"] = attachments
        with self._client() as client:
            resp = client.post(url, headers=self._headers(), params=params, json=payload)
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            return data if isinstance(data, dict) else {"raw": data}

    def pin_message(
        self,
        *,
        chat_id: int | str,
        message_id: str,
        notify: bool = True,
    ) -> dict[str, Any]:
        """PUT /chats/{chatId}/pin — закрепить пост в канале."""
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "no MAX_BOT_TOKEN"}
        endpoint = f"{self.api_base}/chats/{chat_id}/pin"
        body = {"message_id": message_id, "notify": notify}
        with self._client() as client:
            resp = client.put(endpoint, headers=self._headers(), json=body)
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            return data if isinstance(data, dict) else {"raw": data}

    def send_chat_action(
        self,
        *,
        chat_id: int | str,
        action: str = "typing_on",
    ) -> dict[str, Any]:
        """POST /chats/{chatId}/actions — индикатор «печатает» в диалоге."""
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "no MAX_BOT_TOKEN"}
        endpoint = f"{self.api_base}/chats/{chat_id}/actions"
        body = {"action": action}
        with self._client() as client:
            resp = client.post(endpoint, headers=self._headers(), json=body)
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            return data if isinstance(data, dict) else {"raw": data}

    def answer_callback(
        self,
        callback_id: str,
        *,
        notification: str | None = None,
        message: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """POST /answers — ответ на нажатие inline-кнопки."""
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "no MAX_BOT_TOKEN"}
        cid = (callback_id or "").strip()
        if not cid:
            return {"ok": False, "skipped": True, "reason": "no callback_id"}
        body: dict[str, Any] = {}
        if notification:
            body["notification"] = notification[:200]
        if message is not None:
            body["message"] = message
        if not body:
            body["notification"] = "OK"
        endpoint = f"{self.api_base}/answers"
        with self._client() as client:
            resp = client.post(
                endpoint,
                headers=self._headers(),
                params={"callback_id": cid},
                json=body,
            )
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
            # bot_added — чтобы получить chat_id канала после добавления бота (GET /chats снят).
            "update_types": [
                "message_created",
                "bot_started",
                "bot_added",
                "bot_removed",
                "message_callback",
            ],
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
