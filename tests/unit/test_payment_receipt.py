"""Сверка чека оплаты с реквизитами и суммой счёта."""

from __future__ import annotations

from sfrfr.services.payment_receipt import (
    evaluate_receipt_text,
    looks_like_receipt,
    match_requisites,
    should_ask_for_receipt,
)


def test_match_org_inn_and_amount() -> None:
    text = (
        "Кассовый чек. Оплата. ООО ПОД ПРИСМОТРОМ ИНН 8905066468 "
        "р/с 40702810467400005864 сумма 3000,00"
    )
    assert looks_like_receipt(text)
    req = match_requisites(text)
    assert req["inn"] is True
    assert req["account"] is True
    assert req["recipient_ok"] is True
    orders = [{"id": "o1", "status": "pending", "amount_rub": 3000, "package_code": "DIAG"}]
    out = evaluate_receipt_text(text, orders)
    assert out["status"] == "confirmed"
    assert out["ask_receipt"] is False
    assert out["order"]["id"] == "o1"


def test_yookassa_receipt_also_ok() -> None:
    text = "Чек ЮKassa. Оплата 5000.00 RUB. ИНН 7750005725"
    orders = [{"id": "o2", "status": "pending", "amount_rub": 5000, "package_code": "ACCOMP"}]
    out = evaluate_receipt_text(text, orders)
    assert out["status"] == "confirmed"
    assert match_requisites(text)["yookassa"] is True


def test_already_paid_does_not_ask_receipt() -> None:
    text = "Чек ООО ПОД ПРИСМОТРОМ ИНН 8905066468 3000"
    orders = [{"id": "o1", "status": "paid", "amount_rub": 3000, "package_code": "DIAG"}]
    assert should_ask_for_receipt(orders) is False
    out = evaluate_receipt_text(text, orders)
    assert out["status"] == "already_paid"
    assert out["ask_receipt"] is False
    assert "не нужно" in out["client_message"]


def test_wrong_inn_is_mismatch() -> None:
    text = "Чек оплата 3000 ИНН 0000000000"
    orders = [{"id": "o1", "status": "pending", "amount_rub": 3000}]
    out = evaluate_receipt_text(text, orders)
    assert out["status"] == "mismatch"
    assert out["order"] is None


def test_ils_text_is_not_a_receipt() -> None:
    text = "Индивидуальный лицевой счет СФР. Страховой стаж 12 лет."
    assert looks_like_receipt(text) is False
    orders = [{"id": "o1", "status": "pending", "amount_rub": 3000}]
    out = evaluate_receipt_text(text, orders)
    assert out["status"] == "not_a_receipt"
    assert out["client_message"] is None
