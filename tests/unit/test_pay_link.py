"""Короткая ссылка ЮKassa и QR."""

from __future__ import annotations

from sfrfr.integrations.payments import parse_yookassa_event
from sfrfr.services.pay_link import (
    is_yookassa_pay_url,
    pay_message_text,
    pay_qr_signature,
    public_qr_url,
    qr_png_bytes,
)


def test_short_yookassa_invoice_url_detected() -> None:
    assert is_yookassa_pay_url("https://yookassa.ru/my/i/Zqncq0lhxSqo/a")
    assert is_yookassa_pay_url("https://yoomoney.ru/checkout/payments/v2/contract?orderId=1")
    assert not is_yookassa_pay_url("https://cabinet.proverkastaza.ru/cases/x?view=payments")


def test_qr_png_is_png() -> None:
    png = qr_png_bytes("https://yookassa.ru/my/i/Zqncq0lhxSqo/a")
    assert png.startswith(b"\x89PNG")
    assert len(png) > 80


def test_qr_signature_stable() -> None:
    first = pay_qr_signature("ord-1")
    assert first == pay_qr_signature("ord-1")
    assert first != pay_qr_signature("ord-2")
    assert "s=" in public_qr_url("ord-1")


def test_pay_message_no_recalculation_promise() -> None:
    text = pay_message_text(service="Диагностика", amount_rub=3000, pay_url="https://yookassa.ru/my/i/x/a")
    assert "3000" in text
    assert "yookassa.ru" in text
    assert "результат не гарантирован" in text.lower()
    assert "увеличим" not in text.lower()


def test_parse_invoice_paid_event() -> None:
    parsed = parse_yookassa_event(
        {
            "event": "invoice.paid",
            "object": {
                "id": "in-1",
                "status": "succeeded",
                "metadata": {"order_id": "ord-1", "case_id": "case-1", "package_code": "DIAG"},
                "payment_details": {"id": "pay-9", "status": "succeeded"},
            },
        }
    )
    assert parsed["provider_payment_id"] == "pay-9"
    assert parsed["paid"] is True
    assert parsed["order_id"] == "ord-1"
    assert parsed["package_code"] == "DIAG"
