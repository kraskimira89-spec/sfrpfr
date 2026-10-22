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
    assert payload["receipt"]["customer"]["email"] == "a@b.ru"
    assert payload["receipt"]["internet"] is True
    # Умный платёж: не фиксируем один способ — порядок СБП/Сбер только в ЛК ЮKassa
    assert "payment_method_data" not in payload
    assert "payment_method_types" not in payload
    assert payload["capture"] is True
    get_settings.cache_clear()


def test_receipt_accepts_phone_without_email(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_post(self: YooKassaClient, path: str, payload: dict[str, Any]) -> tuple[int, dict]:
        captured["payload"] = payload
        return 200, {"id": "pay-phone", "status": "pending", "confirmation": {}}

    monkeypatch.setattr(YooKassaClient, "_post", fake_post)
    monkeypatch.setenv("YOOKASSA_SEND_RECEIPT", "true")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    client = YooKassaClient(shop_id="shop", secret_key="secret")
    client.create_payment(
        amount_rub=3000,
        description="diag",
        return_url="https://cabinet.proverkastaza.ru/",
        customer_phone="+7 (909) 195-04-08",
    )
    customer = captured["payload"]["receipt"]["customer"]
    assert "email" not in customer
    assert customer["phone"] == "79091950408"
    get_settings.cache_clear()


def test_create_receipt_retry_payload(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_post(self: YooKassaClient, path: str, payload: dict[str, Any]) -> tuple[int, dict]:
        captured["path"] = path
        captured["payload"] = payload
        return 200, {"id": "rt-1", "status": "pending", "type": "payment"}

    monkeypatch.setattr(YooKassaClient, "_post", fake_post)
    monkeypatch.setenv("YOOKASSA_SEND_RECEIPT", "true")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    client = YooKassaClient(shop_id="shop", secret_key="secret")
    out = client.create_receipt(
        payment_id="326bea92-000f-5001-8000-18aadc720fe4",
        amount_rub=3000.0,
        description="Проверка стажа — Диагностика",
        customer_email="client@example.com",
    )
    assert out["ok"] is True
    assert captured["path"] == "/receipts"
    body = captured["payload"]
    assert body["payment_id"] == "326bea92-000f-5001-8000-18aadc720fe4"
    assert body["type"] == "payment"
    assert body["send"] is True
    assert body["internet"] is True
    assert body["settlements"][0]["type"] == "cashless"
    assert body["settlements"][0]["amount"]["value"] == "3000.00"
    get_settings.cache_clear()


def test_ensure_receipt_skips_when_already_succeeded(monkeypatch: Any) -> None:
    client = YooKassaClient(shop_id="shop", secret_key="secret")
    monkeypatch.setattr(
        client,
        "fetch_payment",
        lambda payment_id: {
            "ok": True,
            "payment": {
                "id": payment_id,
                "status": "succeeded",
                "receipt_registration": "succeeded",
                "amount": {"value": "3000.00", "currency": "RUB"},
                "description": "diag",
            },
        },
    )
    called: list[str] = []
    monkeypatch.setattr(
        client,
        "create_receipt",
        lambda **kwargs: called.append("x") or {"ok": True},
    )
    out = client.ensure_payment_receipt(
        payment_id="pay-1",
        customer_email="a@b.ru",
    )
    assert out["ok"] is True
    assert out.get("skipped") is True
    assert called == []


def test_parse_yookassa_event_receipt_registration() -> None:
    parsed = parse_yookassa_event(
        {
            "event": "payment.succeeded",
            "object": {
                "id": "pay-reg",
                "status": "succeeded",
                "paid": True,
                "receipt_registration": "canceled",
                "amount": {"value": "3000.00"},
                "metadata": {"order_id": "o1"},
            },
        }
    )
    assert parsed["receipt_registration"] == "canceled"
