"""Yandex SmartCaptcha: серверная проверка токена (ТЗ-15, пилот staging)."""

from __future__ import annotations

from typing import Any

import httpx

from sfrfr.core.config import get_settings

_VALIDATE_URL = "https://smartcaptcha.cloud.yandex.ru/validate"


class SmartCaptchaVerifier:
    def __init__(
        self,
        *,
        server_key: str | None = None,
        client_key: str | None = None,
    ) -> None:
        settings = get_settings()
        self.server_key = (
            server_key if server_key is not None else settings.smartcaptcha_server_key
        ).strip()
        self.client_key = (
            client_key if client_key is not None else settings.smartcaptcha_client_key
        ).strip()

    @property
    def configured(self) -> bool:
        return bool(self.server_key)

    def verify(
        self,
        token: str,
        *,
        user_ip: str | None = None,
    ) -> dict[str, Any]:
        """Вернуть ok; не логировать token/server_key."""
        if not self.configured:
            return {
                "ok": False,
                "skipped": True,
                "reason": "SmartCaptcha not configured",
            }
        tok = (token or "").strip()
        if not tok:
            return {"ok": False, "error": "empty_token"}

        data: dict[str, str] = {"secret": self.server_key, "token": tok}
        if user_ip:
            data["ip"] = user_ip
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(_VALIDATE_URL, data=data)
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "status_code": resp.status_code,
                    "error": (resp.text or "")[:400],
                }
            body = resp.json() or {}
            status = str(body.get("status") or "").lower()
            ok = status == "ok"
            return {
                "ok": ok,
                "status": status,
                "host": body.get("host"),
                "message": body.get("message"),
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
