"""Тесты ЮKassa parse / receipt payload."""

from __future__ import annotations

from typing import Any

from sfrfr.api.routes.payments import _return_url
from sfrfr.integrations.payments import (
    YooKassaClient,
    check_fiscalization_alignment,
    parse_yookassa_event,
)
from sfrfr.integrations.payments.notify import (
    format_amocrm_payment_note,
    format_payment_succeeded_message,
)
from sfrfr.services.public_tariffs import PAYMENT_PURPOSE, payment_description


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


def test_payment_purpose_uses_current_brand() -> None:
    assert "Проверка стажа" in PAYMENT_PURPOSE
    assert "proverkastaza.ru" in PAYMENT_PURPOSE
    assert "dorogadobra" not in PAYMENT_PURPOSE.lower()
    assert "taxi" not in PAYMENT_PURPOSE.lower()


def test_payment_description_diag_brand_and_service() -> None:
    text = payment_description("DIAG")
    assert text.startswith("Проверка стажа")
    assert "Диагностика" in text
    assert "dorogadobra" not in text.lower()
    assert len(text) <= 128


def test_payment_description_fallback_purpose() -> None:
    text = payment_description("")
    assert text == PAYMENT_PURPOSE[:128]
    assert "Проверка стажа" in text


def test_return_url_uses_cabinet_proverkastaza(monkeypatch: Any) -> None:
    monkeypatch.setenv("YOOKASSA_RETURN_URL", "")
    monkeypatch.setenv("CABINET_PUBLIC_URL", "https://cabinet.proverkastaza.ru")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    url = _return_url("case-abc", "web_cabinet")
    assert "cabinet.proverkastaza.ru" in url
    assert "dorogadobra" not in url.lower()
    assert "view=payments" in url
    get_settings.cache_clear()


def test_create_payment_payload_description_and_return_url(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_post(self: YooKassaClient, path: str, payload: dict[str, Any]) -> tuple[int, dict]:
        captured["path"] = path
        captured["payload"] = payload
        return 200, {
            "id": "pay-brand",
            "status": "pending",
            "confirmation": {"confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=1"},
        }

    monkeypatch.setattr(YooKassaClient, "_post", fake_post)
    monkeypatch.setenv("YOOKASSA_SEND_RECEIPT", "true")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    client = YooKassaClient(shop_id="shop", secret_key="secret")
    desc = payment_description("DIAG")
    result = client.create_payment(
        amount_rub=3000,
        description=desc,
        return_url="https://cabinet.proverkastaza.ru/cases/x?view=payments&paid=1",
        customer_email="a@b.ru",
    )
    assert result["ok"] is True
    payload = captured["payload"]
    assert payload["description"] == desc
    assert "Проверка стажа" in payload["description"]
    assert payload["confirmation"]["return_url"].startswith("https://cabinet.proverkastaza.ru")
    assert payload["receipt"]["items"][0]["description"] == desc[:128]
    get_settings.cache_clear()
