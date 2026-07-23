"""Интеграция Taganay CRM: минимум контактов, связь по case_id."""

from __future__ import annotations

from typing import Any

import httpx

from sfrfr.core.config import get_settings


class TaganayClient:
    """
    Исходящий sync в Taganay (webhook/API URL).
    Файлы и OCR не передаём — только case_id, этап и минимальный контакт.
    """

    def __init__(
        self,
        *,
        webhook_url: str | None = None,
        api_token: str | None = None,
    ) -> None:
        settings = get_settings()
        raw = webhook_url if webhook_url is not None else settings.taganay_webhook_url
        self.webhook_url = raw.rstrip("/") if raw else ""
        self.api_token = api_token if api_token is not None else settings.taganay_api_token

    @property
    def available(self) -> bool:
        return bool(self.webhook_url)

    def sync_case(
        self,
        *,
        case_id: str,
        b2c_status: str,
        pipeline_status: str,
        full_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        task: str | None = None,
    ) -> dict[str, Any]:
        """Создать/обновить карточку. ПДн-контакты — опционально и минимально."""
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "no TAGANAY_WEBHOOK_URL"}

        payload: dict[str, Any] = {
            "case_id": case_id,
            "b2c_status": b2c_status,
            "pipeline_status": pipeline_status,
            "source": "sfrfr",
        }
        # Минимум для работы оператора в CRM (не файлы/OCR/СНИЛС).
        if full_name:
            payload["full_name"] = full_name
        if phone:
            payload["phone"] = phone
        if email:
            payload["email"] = email
        if task:
            payload["task"] = task

        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.post(self.webhook_url, json=payload, headers=headers)
            ok = 200 <= response.status_code < 300
            body: Any
            try:
                body = response.json()
            except Exception:  # noqa: BLE001
                body = {"text": response.text[:200]}
            return {
                "ok": ok,
                "status_code": response.status_code,
                "case_id": case_id,
                "response": body,
            }
        except Exception as exc:  # noqa: BLE001 - не блокируем дело
            return {"ok": False, "case_id": case_id, "error": type(exc).__name__}


def sync_case_to_taganay(
    *,
    case_id: str,
    b2c_status: str,
    pipeline_status: str,
    full_name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    task: str | None = None,
) -> dict[str, Any]:
    return TaganayClient().sync_case(
        case_id=case_id,
        b2c_status=b2c_status,
        pipeline_status=pipeline_status,
        full_name=full_name,
        phone=phone,
        email=email,
        task=task,
    )
