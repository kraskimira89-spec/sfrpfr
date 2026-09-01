"""Тесты ЮKassa parse / receipt payload."""

from __future__ import annotations

from sfrfr.integrations.payments import (
    YooKassaClient,
    check_fiscalization_alignment,
    parse_yookassa_event,
)
from sfrfr.integrations.payments.notify import (
    format_amocrm_payment_note,
    format_payment_succeeded_message,
)


def test_parse_yookassa_event_extracts_metadata() -> None:
    payload = {
        "event": "payment.succeeded",
        "object": {
            "id": "pay-1",
            "status": "succeeded",
            "paid": True,
            "amount": {"value": "3000.00", "currency": "RUB"},
            "metadata": {
                "order_id": "ord-1",
                "case_id": "case-1",
                "package_code": "DIAG",
                "channel": "max_miniapp",
            },
        },
    }
    parsed = parse_yookassa_event(payload)
    assert parsed["provider_payment_id"] == "pay-1"
    assert parsed["package_code"] == "DIAG"
    assert parsed["channel"] == "max_miniapp"
    assert parsed["paid"] is True


def test_yookassa_unavailable_without_keys() -> None:
    client = YooKassaClient(shop_id="", secret_key="")
    assert client.available is False
    result = client.create_payment(
        amount_rub=100,
        description="test",
        return_url="https://example.com",
    )
    assert result["ok"] is False
    assert result.get("skipped") is True


def test_format_payment_succeeded_message_mentions_receipt_and_cabinet() -> None:
    text = format_payment_succeeded_message(
        case_id="11111111-2222-3333-4444-555555555555",
        package_code="DIAG",
        amount_value="3000.00",
        customer_email="client@example.com",
        receipt_via_yookassa=True,
    )
    assert "Оплата получена" in text
    assert "диагностика" in text
    assert "Чек присылать не нужно" in text
    assert "Оплаты" in text
    assert "кабинет" in text.lower()


def test_format_amocrm_payment_note_is_ops_not_fiscal() -> None:
    note = format_amocrm_payment_note(
        case_id="case-1",
        package_code="DIAG",
        amount_value="3000.00",
        provider_payment_id="pay-1",
    )
    assert "оплата прошла" in note
    assert "ЮKassa" in note
    assert "не через CRM" in note


def test_fiscalization_alignment_ok_for_evotor_with_receipt() -> None:
    res = check_fiscalization_alignment(
        fiscalization_enabled=True,
        fiscal_provider="evotor",
        send_receipt=True,
    )
    assert res["ok"] is True
    assert res["warnings"] == []


def test_fiscalization_alignment_fails_without_receipt() -> None:
    res = check_fiscalization_alignment(
        fiscalization_enabled=True,
        fiscal_provider="evotor",
        send_receipt=False,
    )
    assert res["ok"] is False
    assert any("SEND_RECEIPT=false" in w for w in res["warnings"])
