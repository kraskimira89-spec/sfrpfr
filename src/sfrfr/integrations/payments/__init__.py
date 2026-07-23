"""ЮKassa: создание платежа и разбор webhook (ТЗ-06)."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from sfrfr.core.config import get_settings


class YooKassaClient:
    """Минимальный клиент ЮKassa API v3."""

    def __init__(
        self,
        *,
        shop_id: str | None = None,
        secret_key: str | None = None,
        api_base: str | None = None,
    ) -> None:
        settings = get_settings()
        self.shop_id = shop_id if shop_id is not None else settings.yookassa_shop_id
        self.secret_key = secret_key if secret_key is not None else settings.yookassa_secret_key
        self.api_base = (
            api_base or settings.yookassa_api_base or "https://api.yookassa.ru/v3"
        ).rstrip("/")

    @property
    def available(self) -> bool:
        return bool(self.shop_id and self.secret_key)

    def create_payment(
        self,
        *,
        amount_rub: float,
        description: str,
        return_url: str,
        metadata: dict[str, Any] | None = None,
        capture: bool = True,
        customer_email: str | None = None,
        vat_code: int = 1,
    ) -> dict[str, Any]:
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "yookassa not configured"}

        payload: dict[str, Any] = {
            "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
            "capture": capture,
            "confirmation": {"type": "redirect", "return_url": return_url},
            "description": description[:128],
            "metadata": metadata or {},
        }
        settings = get_settings()
        if settings.yookassa_send_receipt and customer_email:
            payload["receipt"] = {
                "customer": {"email": customer_email},
                "items": [
                    {
                        "description": description[:128],
                        "quantity": "1.00",
                        "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                        "vat_code": vat_code,
                        "payment_mode": "full_payment",
                        "payment_subject": "service",
                    }
                ],
            }
        headers = {
            "Idempotence-Key": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.api_base}/payments",
                json=payload,
                headers=headers,
                auth=(self.shop_id, self.secret_key),
            )
        data = response.json() if response.content else {}
        return {
            "ok": response.status_code < 300,
            "status_code": response.status_code,
            "payment": data,
            "payment_id": data.get("id"),
            "confirmation_url": (data.get("confirmation") or {}).get("confirmation_url"),
            "status": data.get("status"),
            "error": data.get("description") or data.get("message"),
        }


def parse_yookassa_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Извлечь статус платежа из уведомления ЮKassa."""
    obj = payload.get("object") if isinstance(payload.get("object"), dict) else payload
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    return {
        "event": payload.get("event"),
        "provider_payment_id": obj.get("id"),
        "status": obj.get("status"),
        "paid": bool(obj.get("paid")),
        "order_id": metadata.get("order_id"),
        "case_id": metadata.get("case_id"),
        "package_code": metadata.get("package_code"),
        "channel": metadata.get("channel"),
        "amount_value": (obj.get("amount") or {}).get("value"),
        "fiscal": (obj.get("receipt") or {}).get("registered") if obj.get("receipt") else None,
    }
