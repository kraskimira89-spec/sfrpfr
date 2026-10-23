"""Тесты ЮKassa parse / receipt payload."""

from __future__ import annotations

from typing import Any

from sfrfr.api.routes.payments import _return_url
from sfrfr.integrations.payments import (
    YooKassaClient,
    check_fiscalization_alignment,
    parse_yookassa_event,
    should_auto_retry_fiscal_receipt,
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


def test_notify_skips_amocrm_when_disabled(monkeypatch: Any) -> None:
    """AMOCRM_ENABLED=0: после оплаты не трогаем amo; чек остаётся у ЮKassa."""
    from sfrfr.integrations.payments import notify as notify_mod

    class _Settings:
        amocrm_enabled = False
        yookassa_send_receipt = True
        max_secure_link_buttons_enabled = False
        secure_action_links_enabled = False

    monkeypatch.setattr(notify_mod, "get_settings", lambda: _Settings())
    monkeypatch.setattr(
        notify_mod,
        "cabinet_case_url",
        lambda case_id, view="payments": f"https://example.test/{case_id}",
    )

    class _FakeTable:
        def select(self, *_a: Any, **_k: Any) -> Any:
            return self

        def eq(self, *_a: Any, **_k: Any) -> Any:
            return self

        def limit(self, *_a: Any, **_k: Any) -> Any:
            return self

        def execute(self) -> Any:
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": "case-1",
                            "clients": {"email": "a@b.c", "max_user_id": None},
                        }
                    ]
                },
            )()

        def insert(self, *_a: Any, **_k: Any) -> Any:
            return self

    class _FakeSb:
        def table(self, _name: str) -> _FakeTable:
            return _FakeTable()

    monkeypatch.setattr(
        "sfrfr.db.session.get_supabase_client",
        lambda: _FakeSb(),
    )

    called: list[str] = []

    def _boom(*_a: Any, **_k: Any) -> dict[str, Any]:
        called.append("amo")
        return {"ok": True}

    monkeypatch.setattr(
        "sfrfr.integrations.amocrm.sync.push_case_to_amocrm",
        _boom,
        raising=False,
    )

    res = notify_mod.notify_payment_succeeded(
        case_id="case-1",
        package_code="DIAG",
        amount_value="3000.00",
        provider_payment_id="pay-1",
    )
    assert res.get("ok") is True
    assert res.get("amocrm_skipped") is True
    assert res.get("amocrm_skip_reason") == "amocrm_disabled"
    assert called == []


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
    assert "taxi-doroga-dobra" not in url.lower()
    assert "dorogadobra" not in url.lower()
    assert "view=payments" in url
    get_settings.cache_clear()


def test_return_url_rewrites_legacy_taxi_env(monkeypatch: Any) -> None:
    # host собран конкатенацией, чтобы массовая замена домена не ломала тест
    legacy = "https://" + "taxi-doroga-dobra" + ".ru/"
    monkeypatch.setenv("YOOKASSA_RETURN_URL", legacy)
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    url = _return_url("case-abc", "web_cabinet")
    assert url.startswith("https://proverkastaza.ru")
    assert "taxi-doroga-dobra" not in url.lower()
    assert "case=case-abc" in url
    get_settings.cache_clear()


def test_return_url_prefers_yookassa_site(monkeypatch: Any) -> None:
    monkeypatch.setenv("YOOKASSA_RETURN_URL", "https://proverkastaza.ru/")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    url = _return_url("case-xyz", "web_cabinet")
    assert url.startswith("https://proverkastaza.ru")
    assert "case=case-xyz" in url
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


def test_create_invoice_includes_return_url(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_post(self: YooKassaClient, path: str, payload: dict[str, Any]) -> tuple[int, dict]:
        captured["path"] = path
        captured["payload"] = payload
        return 200, {
            "id": "in-1",
            "status": "pending",
            "delivery_method": {"type": "self", "url": "https://yookassa.ru/my/i/x"},
        }

    monkeypatch.setattr(YooKassaClient, "_post", fake_post)
    monkeypatch.setenv("YOOKASSA_SEND_RECEIPT", "false")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    client = YooKassaClient(shop_id="shop", secret_key="secret")
    result = client.create_invoice(
        amount_rub=1,
        description="test",
        expires_at="2030-01-01T00:00:00.000Z",
        return_url="https://proverkastaza.ru/?case=c1&view=payments&paid=1",
    )
    assert result["ok"] is True
    assert captured["path"] == "/invoices"
    conf = captured["payload"]["payment_data"]["confirmation"]
    assert conf["type"] == "redirect"
    assert conf["return_url"].startswith("https://proverkastaza.ru/")
    assert "taxi-doroga-dobra" not in conf["return_url"]
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


def test_should_auto_retry_fiscal_only_after_canceled() -> None:
    """Webhook не должен дергать ensure при pending/пусто (гонка FD 777+778)."""
    assert should_auto_retry_fiscal_receipt("canceled") is True
    assert should_auto_retry_fiscal_receipt("cancelled") is True
    assert should_auto_retry_fiscal_receipt("pending") is False
    assert should_auto_retry_fiscal_receipt("succeeded") is False
    assert should_auto_retry_fiscal_receipt("") is False
    assert should_auto_retry_fiscal_receipt(None) is False


def test_ensure_receipt_skips_when_registration_pending_even_if_list_empty(
    monkeypatch: Any,
) -> None:
    """Гонка SUPPORT 8000: webhook при reg=pending, GET /receipts ещё пуст.

    Чек из invoice уже летит в Evotor (FD 777 без settlements); POST /receipts
    даёт второй type=payment (FD 778 с settlements). Pending = не создавать.
    """
    client = YooKassaClient(shop_id="shop", secret_key="secret")
    monkeypatch.setattr(
        client,
        "fetch_payment",
        lambda payment_id: {
            "ok": True,
            "payment": {
                "id": payment_id,
                "status": "succeeded",
                "receipt_registration": "pending",
                "amount": {"value": "8000.00", "currency": "RUB"},
                "description": "support",
            },
        },
    )
    monkeypatch.setattr(
        client,
        "list_receipts",
        lambda payment_id: {"ok": True, "items": []},
    )
    called: list[str] = []
    monkeypatch.setattr(
        client,
        "create_receipt",
        lambda **kwargs: called.append("x") or {"ok": True},
    )
    out = client.ensure_payment_receipt(
        payment_id="326d821f-000f-5001-9000-1a272330e2d3",
        customer_email="nataliylo@yandex.ru",
    )
    assert out["ok"] is True
    assert out.get("skipped") is True
    assert out.get("reason") == "registration_pending"
    assert called == []


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


def test_ensure_receipt_skips_when_succeeded_type_payment_exists(
    monkeypatch: Any,
) -> None:
    """Один payment_id не должен получить второй succeeded type=payment.

    Кейс FD 770/771: payment.receipt_registration ещё canceled, но чек из
    create_payment уже succeeded — автоповтор POST /receipts запрещён.
    """
    client = YooKassaClient(shop_id="shop", secret_key="secret")
    monkeypatch.setattr(
        client,
        "fetch_payment",
        lambda payment_id: {
            "ok": True,
            "payment": {
                "id": payment_id,
                "status": "succeeded",
                "receipt_registration": "canceled",
                "amount": {"value": "5.00", "currency": "RUB"},
                "description": "docs",
            },
        },
    )
    monkeypatch.setattr(
        client,
        "list_receipts",
        lambda payment_id: {
            "ok": True,
            "items": [
                {
                    "id": "ra-existing",
                    "type": "payment",
                    "status": "succeeded",
                    "payment_id": payment_id,
                    "fiscal_document_number": "770",
                }
            ],
        },
    )
    called: list[str] = []
    monkeypatch.setattr(
        client,
        "create_receipt",
        lambda **kwargs: called.append("x") or {"ok": True},
    )
    out = client.ensure_payment_receipt(
        payment_id="326d4ecc-000f-5000-8000-0000000003b4",
        customer_email="a@b.ru",
    )
    assert out["ok"] is True
    assert out.get("skipped") is True
    assert out.get("reason") == "succeeded_payment_receipt_exists"
    assert called == []


def test_ensure_receipt_retries_only_without_succeeded_payment(
    monkeypatch: Any,
) -> None:
    client = YooKassaClient(shop_id="shop", secret_key="secret")
    monkeypatch.setattr(
        client,
        "fetch_payment",
        lambda payment_id: {
            "ok": True,
            "payment": {
                "id": payment_id,
                "status": "succeeded",
                "receipt_registration": "canceled",
                "amount": {"value": "5.00", "currency": "RUB"},
                "description": "docs",
            },
        },
    )
    monkeypatch.setattr(
        client,
        "list_receipts",
        lambda payment_id: {
            "ok": True,
            "items": [
                {
                    "id": "ra-canceled",
                    "type": "payment",
                    "status": "canceled",
                    "payment_id": payment_id,
                }
            ],
        },
    )
    monkeypatch.setenv("YOOKASSA_SEND_RECEIPT", "true")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    called: list[dict[str, Any]] = []

    def fake_create(**kwargs: Any) -> dict[str, Any]:
        called.append(kwargs)
        return {"ok": True, "receipt_id": "ra-new", "status": "pending"}

    monkeypatch.setattr(client, "create_receipt", fake_create)
    out = client.ensure_payment_receipt(
        payment_id="pay-retry",
        customer_email="a@b.ru",
    )
    assert out["ok"] is True
    assert len(called) == 1
    assert called[0]["payment_id"] == "pay-retry"
    get_settings.cache_clear()


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
