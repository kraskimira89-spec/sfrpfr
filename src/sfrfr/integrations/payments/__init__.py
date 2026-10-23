"""ЮKassa: создание платежа и разбор webhook (ТЗ-06)."""

from __future__ import annotations

import re
import uuid
from typing import Any

import httpx

from sfrfr.core.config import get_settings

_PHONE_DIGITS = re.compile(r"\D+")


def normalize_receipt_phone(phone: str | None) -> str | None:
    """Телефон для receipt.customer: 7XXXXXXXXXX (ЮKassa/ККТ)."""
    digits = _PHONE_DIGITS.sub("", str(phone or ""))
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10 and digits.startswith("9"):
        digits = "7" + digits
    if len(digits) == 11 and digits.startswith("7"):
        return digits
    return None


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

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        """GET /v3/payments/{id} — статус и receipt_registration."""
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "yookassa not configured"}
        pid = str(payment_id or "").strip()
        if not pid:
            return {"ok": False, "error": "payment_id required"}
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{self.api_base}/payments/{pid}",
                auth=(self.shop_id, self.secret_key),
            )
        raw = response.json() if response.content else {}
        data: dict[str, Any] = raw if isinstance(raw, dict) else {}
        return {
            "ok": response.status_code < 300,
            "status_code": response.status_code,
            "payment": data,
            "error": data.get("description") or data.get("message"),
        }

    def list_receipts(self, payment_id: str) -> dict[str, Any]:
        """GET /v3/receipts?payment_id= — чеки платежа (дедуп автоповтора)."""
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "yookassa not configured"}
        pid = str(payment_id or "").strip()
        if not pid:
            return {"ok": False, "error": "payment_id required"}
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{self.api_base}/receipts",
                params={"payment_id": pid},
                auth=(self.shop_id, self.secret_key),
            )
        raw = response.json() if response.content else {}
        data: dict[str, Any] = raw if isinstance(raw, dict) else {}
        items_raw = data.get("items")
        items: list[Any] = items_raw if isinstance(items_raw, list) else []
        return {
            "ok": response.status_code < 300,
            "status_code": response.status_code,
            "items": [row for row in items if isinstance(row, dict)],
            "error": data.get("description") or data.get("message"),
        }

    def _receipt(
        self,
        *,
        amount_rub: float,
        description: str,
        customer_email: str | None = None,
        customer_phone: str | None = None,
        vat_code: int | None = None,
    ) -> dict[str, Any] | None:
        settings = get_settings()
        if not settings.yookassa_send_receipt:
            return None
        email = (customer_email or "").strip() or None
        phone = normalize_receipt_phone(customer_phone)
        if not email and not phone:
            return None
        customer: dict[str, str] = {}
        if email:
            customer["email"] = email
        if phone:
            customer["phone"] = phone
        code = int(vat_code if vat_code is not None else settings.yookassa_vat_code or 1)
        return {
            "customer": customer,
            "items": [
                {
                    "description": description[:128],
                    "quantity": "1.00",
                    "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                    "vat_code": code,
                    "payment_mode": "full_payment",
                    "payment_subject": "service",
                }
            ],
            # интернет-расчёт — для онлайн-кассы Evotor / 54-ФЗ
            "internet": True,
        }

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        idempotence_key: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        key = (idempotence_key or "").strip() or str(uuid.uuid4())
        if len(key) > 64:
            return 0, {
                "error": "idempotence_key longer than 64 characters",
                "phase": "pre_post",
            }
        headers = {
            "Idempotence-Key": key,
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.api_base}{path}",
                    json=payload,
                    headers=headers,
                    auth=(self.shop_id, self.secret_key),
                )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            return 0, {"error": str(exc) or type(exc).__name__, "phase": "transport"}
        # 502/прокси с HTML: не ронять после POST — пустой data → classify → unknown.
        data: dict[str, Any] = {}
        if response.content:
            try:
                parsed = response.json()
                if isinstance(parsed, dict):
                    data = parsed
            except ValueError:
                data = {}
        return response.status_code, data

    def create_payment(
        self,
        *,
        amount_rub: float,
        description: str,
        return_url: str,
        metadata: dict[str, Any] | None = None,
        capture: bool = True,
        customer_email: str | None = None,
        customer_phone: str | None = None,
        vat_code: int | None = None,
    ) -> dict[str, Any]:
        """Умный платёж (redirect): без payment_method_data — иначе один способ вместо списка.

        Порядок СБП→SberPay→остальное задаётся только в ЛК/у менеджера ЮKassa
        (docs/yookassa-setup.md). capture=True нужен, чтобы СБП был доступен.
        """
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
            customer_phone=customer_phone,
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
        customer_phone: str | None = None,
        vat_code: int | None = None,
        capture: bool = True,
        return_url: str | None = None,
    ) -> dict[str, Any]:
        """Счёт ЮKassa: короткая ссылка delivery_method.url (self, без SMS/email).

        return_url в payment_data.confirmation — если API примет; иначе после оплаты
        ЮKassa берёт сайт магазина из ЛК (должен быть proverkastaza.ru).
        """
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "yookassa not configured"}
        meta = metadata or {}
        payment_data: dict[str, Any] = {
            "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
            "capture": capture,
            "description": description[:128],
            "metadata": meta,
        }
        if return_url:
            payment_data["confirmation"] = {
                "type": "redirect",
                "return_url": return_url,
            }
        receipt = self._receipt(
            amount_rub=amount_rub,
            description=description,
            customer_email=customer_email,
            customer_phone=customer_phone,
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

    def create_receipt(
        self,
        *,
        payment_id: str,
        amount_rub: float,
        description: str,
        customer_email: str | None = None,
        customer_phone: str | None = None,
        vat_code: int | None = None,
        idempotence_key: str | None = None,
        body_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """POST /v3/receipts — повторная фискализация после сбоя доставки в ККТ.

        ``body_snapshot`` / ``idempotence_key`` — только reconcile/CLI (SFRFR-93);
        webhook оставляет uuid4 и сборку тела как раньше.
        """
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "yookassa not configured"}
        if body_snapshot is not None:
            payload = dict(body_snapshot)
        else:
            receipt = self._receipt(
                amount_rub=amount_rub,
                description=description,
                customer_email=customer_email,
                customer_phone=customer_phone,
                vat_code=vat_code,
            )
            if not receipt:
                return {
                    "ok": False,
                    "error": "receipt requires YOOKASSA_SEND_RECEIPT and email or phone",
                }
            payload = {
                "type": "payment",
                "payment_id": str(payment_id).strip(),
                "send": True,
                "customer": receipt["customer"],
                "items": receipt["items"],
                "internet": True,
                "settlements": [
                    {
                        "type": "cashless",
                        "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                    }
                ],
            }
        status_code, data = self._post(
            "/receipts", payload, idempotence_key=idempotence_key
        )
        # phase: job отличает pre_post / transport / http (не по тексту ошибки).
        if status_code == 0 and data.get("error"):
            phase = str(data.get("phase") or "pre_post")
            if phase not in {"pre_post", "transport"}:
                phase = "pre_post"
            return {
                "ok": False,
                "phase": phase,
                "error": str(data.get("error")),
            }
        # request_body с PII не возвращаем: webhook логирует error, CLI echo
        # результата; job уже имеет body_snapshot для payload в БД.
        return {
            "ok": status_code < 300,
            "phase": "http",
            "status_code": status_code,
            "receipt": data,
            "receipt_id": data.get("id"),
            "status": data.get("status"),
            "error": data.get("description") or data.get("message"),
        }

    def ensure_payment_receipt(
        self,
        *,
        payment_id: str,
        customer_email: str | None = None,
        customer_phone: str | None = None,
        description: str | None = None,
        amount_rub: float | None = None,
        idempotence_key: str | None = None,
        body_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Повтор POST /receipts только если нет успешного type=payment чека.

        Поле payment.receipt_registration может оставаться canceled после FD
        (см. FD 770/771) — ориентир: список receipts, не только registration.
        """
        fetched = self.fetch_payment(payment_id)
        if not fetched.get("ok"):
            return {
                "ok": False,
                "error": fetched.get("error") or "payment fetch failed",
                "status_code": fetched.get("status_code"),
            }
        raw_payment = fetched.get("payment")
        payment: dict[str, Any] = (
            raw_payment if isinstance(raw_payment, dict) else {}
        )
        pid = str(payment.get("id") or payment_id)
        reg = str(payment.get("receipt_registration") or "").strip().lower()
        if reg == "succeeded":
            return {
                "ok": True,
                "skipped": True,
                "reason": "already_registered",
                "registration": reg,
            }
        # pending = чек из create_payment/invoice уже в полёте (Evotor).
        # POST /receipts здесь даёт второй type=payment (FD 777+778 SUPPORT 8000).
        if reg == "pending":
            return {
                "ok": True,
                "skipped": True,
                "reason": "registration_pending",
                "registration": reg,
            }
        listed = self.list_receipts(pid)
        if not listed.get("ok"):
            return {
                "ok": False,
                "error": listed.get("error") or "receipts list failed",
                "status_code": listed.get("status_code"),
            }
        gate = payment_receipt_retry_gate(listed.get("items") or [])
        if gate.get("skip"):
            return {
                "ok": True,
                "skipped": True,
                "reason": str(gate.get("reason") or "receipt_exists"),
                "registration": reg,
                "receipt_id": gate.get("receipt_id"),
            }
        status_value = str(payment.get("status") or "")
        if status_value not in {"succeeded", "waiting_for_capture"}:
            return {
                "ok": False,
                "skipped": True,
                "reason": f"payment_status={status_value or 'unknown'}",
            }
        raw_amount = payment.get("amount")
        amount: dict[str, Any] = raw_amount if isinstance(raw_amount, dict) else {}
        value_raw = amount.get("value")
        try:
            amount_value = float(amount_rub if amount_rub is not None else value_raw or 0)
        except (TypeError, ValueError):
            amount_value = 0.0
        if amount_value <= 0 and body_snapshot is None:
            return {"ok": False, "error": "amount missing"}
        desc = (
            (description or "").strip()
            or str(payment.get("description") or "").strip()
            or "Оплата услуг"
        )
        return self.create_receipt(
            payment_id=pid,
            amount_rub=amount_value if amount_value > 0 else 0.0,
            description=desc,
            customer_email=customer_email,
            customer_phone=customer_phone,
            idempotence_key=idempotence_key,
            body_snapshot=body_snapshot,
        )


def should_auto_retry_fiscal_receipt(receipt_registration: str | None) -> bool:
    """Webhook: автоповтор только после явного сбоя регистрации в ЮKassa.

    ``pending`` / пусто — фискализация с чека create_payment/invoice уже идёт;
    повторный POST /receipts даёт второй succeeded type=payment (FD 777+778).
    ``canceled`` — письмо «пробейте вручную»; тогда ensure + gate по GET /receipts.
    """
    reg = str(receipt_registration or "").strip().lower()
    return reg in {"canceled", "cancelled"}


def payment_receipt_retry_gate(items: list[Any]) -> dict[str, Any]:
    """Повтор type=payment запрещён, если уже есть succeeded (или pending в полёте)."""
    for row in items:
        if not isinstance(row, dict):
            continue
        if str(row.get("type") or "").strip().lower() != "payment":
            continue
        status = str(row.get("status") or "").strip().lower()
        rid = str(row.get("id") or "") or None
        if status == "succeeded":
            return {
                "skip": True,
                "reason": "succeeded_payment_receipt_exists",
                "receipt_id": rid,
            }
        if status == "pending":
            return {
                "skip": True,
                "reason": "pending_payment_receipt_exists",
                "receipt_id": rid,
            }
    return {"skip": False}


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
        "receipt_registration": obj.get("receipt_registration"),
    }
