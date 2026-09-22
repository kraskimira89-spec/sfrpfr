"""Идемпотентность старта оплаты (B1): повторный /pay не создаёт второй платёж."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from sfrfr.api.routes import payments as payments_route
from sfrfr.api.routes.payments import PayOrderRequest, start_order_payment
from sfrfr.db.case_repository import PaymentSlotConflict


class FakePrincipal:
    user_id = "user-1"
    email = "client@example.ru"
    is_staff = False

    def audit_actor_id(self) -> str:
        return "user-1"


class FakeRepo:
    def __init__(self, *, order: dict | None, active_payment: dict | None) -> None:
        self.order = order
        self.active_payment = active_payment
        self.created_records: list[dict[str, Any]] = []
        self.reservation_id = "res-1"
        self.failed_ids: list[str] = []
        self.updated: list[dict[str, Any]] = []

    def require_case(self, _principal: Any, case_id: str) -> dict:
        return {"id": case_id}

    def get_order(self, _case_id: str, _order_id: str) -> dict | None:
        return self.order

    def create_payment_reservation(self, **kwargs: Any) -> dict:
        if self.active_payment:
            raise PaymentSlotConflict("active payment already exists for order")
        self.created_records.append(kwargs)
        return {"id": self.reservation_id, "status": "pending", **kwargs}

    def update_payment_reservation(self, payment_id: str, **kwargs: Any) -> dict:
        self.updated.append({"id": payment_id, **kwargs})
        return {"id": payment_id, **kwargs}

    def mark_payment_failed(self, payment_id: str) -> dict:
        self.failed_ids.append(payment_id)
        return {"id": payment_id, "status": "failed"}


class FakeYooKassa:
    calls = 0

    def __init__(self) -> None:
        self.available = True

    def create_payment(self, **_kwargs: Any) -> dict:
        FakeYooKassa.calls += 1
        return {
            "ok": True,
            "payment_id": f"prov-{FakeYooKassa.calls}",
            "confirmation_url": "https://yoomoney.ru/checkout/payments?id=x",
            "status": "pending",
        }


@pytest.fixture()
def _fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeYooKassa.calls = 0
    monkeypatch.setattr(payments_route, "YooKassaClient", FakeYooKassa)


def _patch_repo(monkeypatch: pytest.MonkeyPatch, repo: FakeRepo) -> None:
    monkeypatch.setattr(payments_route, "_repo", lambda: repo)


_ORDER = {
    "id": "o1",
    "case_id": "c1",
    "package_code": "DIAG",
    "amount_rub": 3000,
    "status": "draft",
}


def test_pay_creates_payment_when_no_active(_fake_client, monkeypatch) -> None:
    repo = FakeRepo(order=dict(_ORDER), active_payment=None)
    _patch_repo(monkeypatch, repo)
    out = start_order_payment(  # type: ignore[arg-type]
        "c1",
        "o1",
        PayOrderRequest(return_channel="web_cabinet"),
        "web_cabinet",
        FakePrincipal(),  # type: ignore[arg-type]
    )
    assert FakeYooKassa.calls == 1
    assert out["confirmation_url"]
    assert len(repo.created_records) == 1


def test_pay_conflict_when_active_payment_exists(_fake_client, monkeypatch) -> None:
    repo = FakeRepo(
        order=dict(_ORDER),
        active_payment={"id": "p1", "order_id": "o1", "status": "pending"},
    )
    _patch_repo(monkeypatch, repo)
    with pytest.raises(HTTPException) as exc:
        start_order_payment(  # type: ignore[arg-type]
            "c1",
            "o1",
            PayOrderRequest(return_channel="web_cabinet"),
            "web_cabinet",
            FakePrincipal(),  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 409
    assert isinstance(exc.value.detail, str)
    assert "Платёж уже" in exc.value.detail
    # Второй платёж провайдеру не отправлялся, запись не создавалась
    assert FakeYooKassa.calls == 0
    assert repo.created_records == []


def test_pay_paid_order_still_400(_fake_client, monkeypatch) -> None:
    order = dict(_ORDER)
    order["status"] = "paid"
    repo = FakeRepo(order=order, active_payment=None)
    _patch_repo(monkeypatch, repo)
    with pytest.raises(HTTPException) as exc:
        start_order_payment(  # type: ignore[arg-type]
            "c1",
            "o1",
            PayOrderRequest(return_channel="web_cabinet"),
            "web_cabinet",
            FakePrincipal(),  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 400
    assert FakeYooKassa.calls == 0
