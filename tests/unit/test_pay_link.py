"""Короткая ссылка ЮKassa и QR."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from sfrfr.integrations.payments import parse_yookassa_event
from sfrfr.services.pay_link import (
    PayLinkError,
    is_yookassa_pay_url,
    issue_and_deliver_pay_link,
    maybe_auto_send_pay_link_after_draft,
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
    text = pay_message_text(
        service="Диагностика",
        amount_rub=3000,
        pay_url="https://yookassa.ru/my/i/x/a",
    )
    assert "3000" in text
    assert "yookassa.ru" in text
    assert "результат не гарантирован" in text.lower()
    assert "чек" in text.lower()
    assert "увеличим" not in text.lower()


def test_parse_invoice_paid_event() -> None:
    parsed = parse_yookassa_event(
        {
            "event": "invoice.paid",
            "object": {
                "id": "in-1",
                "status": "succeeded",
                "metadata": {
                    "order_id": "ord-1",
                    "case_id": "case-1",
                    "package_code": "DIAG",
                },
                "payment_details": {"id": "pay-9", "status": "succeeded"},
            },
        }
    )
    assert parsed["provider_payment_id"] == "pay-9"
    assert parsed["paid"] is True
    assert parsed["order_id"] == "ord-1"
    assert parsed["package_code"] == "DIAG"


def test_issue_and_deliver_sends_max_with_qr() -> None:
    order = {
        "id": "11111111-1111-1111-1111-111111111111",
        "case_id": "22222222-2222-2222-2222-222222222222",
        "amount_rub": 3000,
        "package_code": "DIAG",
        "service_label": "Диагностика",
        "status": "draft",
        "pay_url": "",
    }
    case = {
        "id": order["case_id"],
        "clients": {"max_user_id": "max-42", "email": ""},
    }
    repo = MagicMock()
    repo.update_order_fields.return_value = {
        **order,
        "status": "pending",
        "pay_url": "https://yookassa.ru/my/i/x",
    }
    settings = MagicMock(
        cabinet_public_url="https://cabinet.example",
        public_base_url="https://api.example",
        app_secret_key="secret",
    )
    with (
        patch("sfrfr.services.pay_link.get_settings", return_value=settings),
        patch(
            "sfrfr.services.pay_link.ensure_yookassa_pay_url",
            return_value={
                "ok": True,
                "pay_url": "https://yookassa.ru/my/i/x",
                "kind": "invoice",
                "invoice_id": "inv-1",
            },
        ),
        patch("sfrfr.services.pay_link.send_pay_link_max") as send_max,
    ):
        out = issue_and_deliver_pay_link(
            repo=repo,
            order=order,
            case=case,
            actor_id="staff-1",
            send_max=True,
            yookassa=MagicMock(),
        )
    assert out["sent"] is True
    assert out["pay_url"].startswith("https://yookassa.ru/")
    assert "/qr.png" in out["qr_url"]
    send_max.assert_called_once()
    assert send_max.call_args.kwargs["max_user_id"] == "max-42"
    assert send_max.call_args.kwargs["qr_url"]
    assert send_max.call_args.kwargs["case_id"] == order["case_id"]


def test_issue_requires_max_user_when_send() -> None:
    order = {
        "id": "11111111-1111-1111-1111-111111111111",
        "case_id": "22222222-2222-2222-2222-222222222222",
        "amount_rub": 3000,
        "status": "draft",
    }
    case: dict[str, Any] = {"id": order["case_id"], "clients": {}}
    repo = MagicMock()
    repo.update_order_fields.return_value = order
    settings = MagicMock(
        cabinet_public_url="https://cabinet.example",
        public_base_url="https://api.example",
        app_secret_key="secret",
    )
    with (
        patch("sfrfr.services.pay_link.get_settings", return_value=settings),
        patch(
            "sfrfr.services.pay_link.ensure_yookassa_pay_url",
            return_value={
                "ok": True,
                "pay_url": "https://yookassa.ru/my/i/x",
                "kind": "invoice",
            },
        ),
        pytest.raises(PayLinkError) as exc,
    ):
        issue_and_deliver_pay_link(
            repo=repo,
            order=order,
            case=case,
            actor_id="staff-1",
            send_max=True,
            yookassa=MagicMock(),
        )
    assert exc.value.code == "client_has_no_max_user_id"


def test_auto_send_off_by_default() -> None:
    settings = MagicMock(max_pay_link_auto_send=False)
    with patch("sfrfr.services.pay_link.get_settings", return_value=settings):
        assert (
            maybe_auto_send_pay_link_after_draft(
                repo=MagicMock(),
                order={"id": "o1"},
                case={"clients": {"max_user_id": "1"}},
                actor_id=None,
            )
            is None
        )
