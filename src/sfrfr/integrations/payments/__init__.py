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

    def fetch_me(self) -> dict[str, Any]:
        """GET /v3/me — статус магазина и фискализации (без секретов в ответе)."""
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "yookassa not configured"}
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{self.api_base}/me",
                auth=(self.shop_id, self.secret_key),
            )
        raw = response.json() if response.content else {}
        data: dict[str, Any] = raw if isinstance(raw, dict) else {}
        fiscal_raw = data.get("fiscalization")
        fiscal: dict[str, Any] = fiscal_raw if isinstance(fiscal_raw, dict) else {}
        return {
            "ok": response.status_code < 300,
            "status_code": response.status_code,
            "account_id": data.get("account_id"),
            "status": data.get("status"),
            "test": data.get("test"),
            "fiscalization_enabled": bool(
                data.get("fiscalization_enabled") or fiscal.get("enabled")
            ),
            "fiscal_provider": fiscal.get("provider"),
            "payment_methods": data.get("payment_methods"),
            "error": data.get("description") or data.get("message"),
        }

    def _receipt(
        self,
        *,
        amount_rub: float,
        description: str,
        customer_email: str | None,
        vat_code: int,
    ) -> dict[str, Any] | None:
        settings = get_settings()
        if not (settings.yookassa_send_receipt and customer_email):
            return None
        return {
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

    def _post(self, path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        headers = {
            "Idempotence-Key": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.api_base}{path}",
                json=payload,
                headers=headers,
                auth=(self.shop_id, self.secret_key),
            )
        data = response.json() if response.content else {}
        return response.status_code, data if isinstance(data, dict) else {}

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
        receipt = self._receipt(
            amount_rub=amount_rub,
            description=description,
            customer_email=customer_email,
            vat_code=vat_code,
        )
        if receipt:
            payload["receipt"] = receipt
        status_code, data = self._post("/payments", payload)
        raw_conf = data.get("confirmation")
        confirmation = raw_conf if isinstance(raw_conf, dict) else {}
        return {
            "ok": status_code < 300,
            "status_code": status_code,
            "payment": data,
            "payment_id": data.get("id"),
            "confirmation_url": confirmation.get("confirmation_url"),
            "status": data.get("status"),
            "error": data.get("description") or data.get("message"),
        }

    def create_invoice(
        self,
        *,
        amount_rub: float,
        description: str,
        metadata: dict[str, Any] | None = None,
        expires_at: str,
        customer_email: str | None = None,
        vat_code: int = 1,
        capture: bool = True,
    ) -> dict[str, Any]:
        """Счёт ЮKassa: короткая ссылка delivery_method.url (self, без SMS/email)."""
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "yookassa not configured"}
        meta = metadata or {}
        payment_data: dict[str, Any] = {
            "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
            "capture": capture,
            "description": description[:128],
            "metadata": meta,
        }
        receipt = self._receipt(
            amount_rub=amount_rub,
            description=description,
            customer_email=customer_email,
            vat_code=vat_code,
        )
        if receipt:
            payment_data["receipt"] = receipt
        payload: dict[str, Any] = {
            "payment_data": payment_data,
            "cart": [
                {
                    "description": description[:128],
                    "price": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                    "quantity": 1.0,
                }
            ],
            "delivery_method_data": {"type": "self"},
            "locale": "ru_RU",
            "expires_at": expires_at,
            "description": description[:128],
            "metadata": meta,
        }
        status_code, data = self._post("/invoices", payload)
        raw_delivery = data.get("delivery_method")
        delivery = raw_delivery if isinstance(raw_delivery, dict) else {}
        return {
            "ok": status_code < 300,
            "status_code": status_code,
            "invoice": data,
            "invoice_id": data.get("id"),
            "pay_url": delivery.get("url"),
            "status": data.get("status"),
            "error": data.get("description") or data.get("message"),
        }


def check_fiscalization_alignment(
    *,
    fiscalization_enabled: bool,
    fiscal_provider: str | None,
    send_receipt: bool,
    expected_provider: str = "evotor",
) -> dict[str, Any]:
    """
    Проверка контура без двойной фискализации.

    Канон SFRFR: одна ККТ-партнёр ЮKassa (сейчас Evotor) → ОФД (Платформа ОФД).
    Не параллелить с «Чеки от ЮKassa» и не слать фискальный чек из MAX/amo.
    """
    warnings: list[str] = []
    provider = (fiscal_provider or "").strip().lower() or None
    if fiscalization_enabled and not send_receipt:
        warnings.append(
            "fiscalization_enabled но YOOKASSA_SEND_RECEIPT=false — "
            "create payment вернёт Receipt is missing"
        )
    if fiscalization_enabled and expected_provider and provider != expected_provider:
        warnings.append(
            f"ожидался fiscal provider={expected_provider}, сейчас {provider or '—'}: "
            "проверьте ЛК ЮKassa (один канал: своя ККТ, не «Чеки от ЮKassa» параллельно)"
        )
    if not fiscalization_enabled and send_receipt:
        warnings.append(
            "SEND_RECEIPT=true при выключенной фискализации — лишний блок receipt "
            "(обычно безопасно, но сверьте ЛК)"
        )
    ok = not any("Receipt is missing" in w or "ожидался fiscal" in w for w in warnings)
    # send_receipt mismatch is hard fail for our shop
    if fiscalization_enabled and not send_receipt:
        ok = False
    return {
        "ok": ok,
        "fiscalization_enabled": fiscalization_enabled,
        "fiscal_provider": provider,
        "send_receipt": send_receipt,
        "expected_provider": expected_provider,
        "contour": "yookassa -> kkt(partner) -> ofd -> fns",
        "ofd_hint": "https://lk.platformaofd.ru/ (prosmotr OFD, ne vtoroj kassir)",
        "warnings": warnings,
    }


def parse_yookassa_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Извлечь статус платежа из уведомления ЮKassa."""
    raw_obj = payload.get("object")
    obj: dict[str, Any] = raw_obj if isinstance(raw_obj, dict) else payload
    raw_meta = obj.get("metadata")
    metadata: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
    amount = obj.get("amount") if isinstance(obj.get("amount"), dict) else {}
    receipt = obj.get("receipt") if isinstance(obj.get("receipt"), dict) else None
    event = str(payload.get("event") or "")
    payment_id = obj.get("id")
    status_value = obj.get("status")
    paid = bool(obj.get("paid"))
    if event.startswith("invoice."):
        raw_details = obj.get("payment_details")
        details: dict[str, Any] = raw_details if isinstance(raw_details, dict) else {}
        payment_id = details.get("id") or payment_id
        status_value = details.get("status") or status_value
        paid = str(status_value or "") == "succeeded" or paid
        raw_payment = obj.get("payment_data")
        payment_data = raw_payment if isinstance(raw_payment, dict) else {}
        raw_nested_meta = payment_data.get("metadata")
        nested_meta = raw_nested_meta if isinstance(raw_nested_meta, dict) else {}
        metadata = {**nested_meta, **metadata}
        raw_nested_amount = payment_data.get("amount")
        nested_amount = raw_nested_amount if isinstance(raw_nested_amount, dict) else {}
        if nested_amount and not amount:
            amount = nested_amount
    return {
        "event": event or payload.get("event"),
        "provider_payment_id": payment_id,
        "status": status_value,
        "paid": paid,
        "order_id": metadata.get("order_id"),
        "case_id": metadata.get("case_id"),
        "package_code": metadata.get("package_code"),
        "channel": metadata.get("channel"),
        "amount_value": amount.get("value") if isinstance(amount, dict) else None,
        "fiscal": receipt.get("registered") if isinstance(receipt, dict) else None,
    }
