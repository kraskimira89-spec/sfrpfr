"""Короткая ссылка и QR на оплату ЮKassa (счёт self, без авторассылки)."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any
from urllib.parse import urlencode

import segno

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.client import MaxBotClient, inline_link_keyboard
from sfrfr.integrations.payments import YooKassaClient
from sfrfr.services.public_tariffs import PAYMENT_PURPOSE, staff_package_label
from sfrfr.services.staff_finance import parse_dt

_YOOKASSA_HOSTS = ("yookassa.ru", "yoomoney.ru")


def is_yookassa_pay_url(url: str | None) -> bool:
    value = (url or "").lower()
    return any(host in value for host in _YOOKASSA_HOSTS)


def pay_qr_signature(order_id: str) -> str:
    secret = get_settings().app_secret_key.encode("utf-8")
    digest = hmac.new(secret, f"pay-qr:{order_id}".encode(), hashlib.sha256).hexdigest()
    return digest[:16]


def public_qr_url(order_id: str) -> str:
    base = get_settings().public_base_url.rstrip("/")
    query = urlencode({"s": pay_qr_signature(order_id)})
    return f"{base}/api/public/pay/{order_id}/qr.png?{query}"


def qr_png_bytes(pay_url: str, *, scale: int = 6) -> bytes:
    qr = segno.make(pay_url, error="m")
    buf = BytesIO()
    qr.save(buf, kind="png", scale=scale, border=2)
    return buf.getvalue()


def _expires_iso(due_at: str | None) -> str:
    due = parse_dt(due_at)
    now = datetime.now(UTC)
    if due is None or due < now + timedelta(hours=2):
        due = now + timedelta(days=3)
    return due.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def ensure_yookassa_pay_url(
    *,
    client: YooKassaClient,
    order: dict[str, Any],
    case: dict[str, Any],
    return_url: str,
    channel: str,
) -> dict[str, Any]:
    """Счёт ЮKassa (короткая ссылка) или fallback на redirect-платёж."""
    existing = str(order.get("pay_url") or "")
    if is_yookassa_pay_url(existing):
        return {"ok": True, "pay_url": existing, "kind": "reuse"}
    if not client.available:
        return {"ok": False, "pay_url": existing, "kind": "unconfigured"}
    amount = float(order.get("amount_rub") or 0)
    if amount <= 0:
        return {"ok": False, "pay_url": existing, "kind": "bad_amount"}
    service = staff_package_label(str(order.get("package_code") or ""), order.get("service_label"))
    description = (service or PAYMENT_PURPOSE)[:128]
    client_row = case.get("clients") or {}
    email = str(client_row.get("email") or "").strip() or None
    meta = {
        "order_id": str(order.get("id") or ""),
        "case_id": str(order.get("case_id") or ""),
        "package_code": str(order.get("package_code") or ""),
        "channel": channel,
    }
    invoice = client.create_invoice(
        amount_rub=amount,
        description=description,
        metadata=meta,
        expires_at=_expires_iso(str(order.get("due_at") or "") or None),
        customer_email=email,
    )
    if invoice.get("ok") and invoice.get("pay_url"):
        return {
            "ok": True,
            "pay_url": str(invoice["pay_url"]),
            "kind": "invoice",
            "invoice_id": invoice.get("invoice_id"),
            "payment_id": None,
        }
    payment = client.create_payment(
        amount_rub=amount,
        description=PAYMENT_PURPOSE,
        return_url=return_url,
        metadata=meta,
        customer_email=email,
    )
    if payment.get("ok") and payment.get("confirmation_url"):
        return {
            "ok": True,
            "pay_url": str(payment["confirmation_url"]),
            "kind": "payment",
            "invoice_id": None,
            "payment_id": payment.get("payment_id"),
            "status": payment.get("status"),
        }
    return {
        "ok": False,
        "pay_url": existing,
        "kind": "failed",
        "error": invoice.get("error") or payment.get("error"),
    }


def pay_message_text(*, service: str, amount_rub: float, pay_url: str) -> str:
    return (
        "Здравствуйте! Счёт на оплату информационно-документарной поддержки "
        f"({service}, {int(amount_rub)} ₽).\n"
        f"{pay_url}\n"
        "Можно открыть ссылку или отсканировать QR. "
        "Решение о пенсии и перерасчёте принимает СФР, результат не гарантирован."
    )


def send_pay_link_max(
    *,
    max_user_id: str,
    service: str,
    amount_rub: float,
    pay_url: str,
    qr_url: str | None = None,
) -> None:
    bot = MaxBotClient()
    if not bot.available:
        raise RuntimeError("max_bot_not_configured")
    text = pay_message_text(service=service, amount_rub=amount_rub, pay_url=pay_url)
    attachments: list[dict[str, Any]] = []
    if qr_url:
        attachments.append({"type": "image", "payload": {"url": qr_url}})
    attachments.extend(inline_link_keyboard("Оплатить", pay_url))
    bot.send_message(text=text, user_id=max_user_id, attachments=attachments)
