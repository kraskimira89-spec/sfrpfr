"""Атомарность active payment (follow-up к B1): reservation-flow /pay.

Проверяет:
- unique conflict / существующий active → 409, provider call не выполняется;
- успешный ответ → ровно одна reservation обновлена;
- достоверная ошибка провайдера → reservation → failed, 502;
- неоднозначный timeout (httpx.HTTPError) → reservation остаётся active,
  повторный provider call не выполняется;
- terminal failed/canceled reservation позволяет новую попытку.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import HTTPException

from sfrfr.api.routes import payments as payments_route
from sfrfr.api.routes.payments import PayOrderRequest, start_order_payment
from sfrfr.db.case_repository import CaseRepository, PaymentSlotConflict


class FakePrincipal:
    user_id = "user-1"
    email = "client@example.ru"
    is_staff = False

    def audit_actor_id(self) -> str:
        return "user-1"


class FakeRepo:
    def __init__(self, *, order: dict | None, active: bool = False) -> None:
        self.order = order
        self.active = active
        self.reservations: list[dict[str, Any]] = []
        self.failed_ids: list[str] = []
        self.updated: list[tuple[str, dict[str, Any]]] = []

    def require_case(self, _principal: Any, case_id: str) -> dict:
        return {"id": case_id}

    def get_order(self, _case_id: str, _order_id: str) -> dict | None:
        return self.order

    def create_payment_reservation(self, **kwargs: Any) -> dict:
        if self.active:
            raise PaymentSlotConflict("active payment already exists for order")
        row = {"id": "res-1", "status": "pending", **kwargs}
        self.reservations.append(row)
        return row

    def update_payment_reservation(self, payment_id: str, **kwargs: Any) -> dict:
        self.updated.append((payment_id, kwargs))
        return {"id": payment_id, **kwargs}

    def mark_payment_failed(self, payment_id: str) -> dict:
        self.failed_ids.append(payment_id)
        return {"id": payment_id, "status": "failed"}


class StubYooKassa:
    calls = 0
    response: dict[str, Any] = {
        "ok": True,
        "payment_id": "prov-1",
        "confirmation_url": "https://yoomoney.ru/checkout/payments?id=x",
        "status": "pending",
    }
    raise_http: bool = False

    def __init__(self) -> None:
        self.available = True

    def create_payment(self, **_kwargs: Any) -> dict:
        StubYooKassa.calls += 1
        if StubYooKassa.raise_http:
            raise httpx.ConnectError("timeout")
        return StubYooKassa.response


@pytest.fixture(autouse=True)
def _stub(monkeypatch: pytest.MonkeyPatch) -> None:
    StubYooKassa.calls = 0
    StubYooKassa.raise_http = False
    StubYooKassa.response = {
        "ok": True,
        "payment_id": "prov-1",
        "confirmation_url": "https://yoomoney.ru/checkout/payments?id=x",
        "status": "pending",
    }
    monkeypatch.setattr(payments_route, "YooKassaClient", StubYooKassa)


def _patch_repo(monkeypatch: pytest.MonkeyPatch, repo: FakeRepo) -> None:
    monkeypatch.setattr(payments_route, "_repo", lambda: repo)


_ORDER = {
    "id": "o1",
    "case_id": "c1",
    "package_code": "DIAG",
    "amount_rub": 3000,
    "status": "draft",
}


def _call() -> Any:
    return start_order_payment(  # type: ignore[arg-type]
        "c1",
        "o1",
        PayOrderRequest(return_channel="web_cabinet"),
        "web_cabinet",
        FakePrincipal(),  # type: ignore[arg-type]
    )


def test_unique_conflict_returns_409_without_provider_call(monkeypatch) -> None:
    repo = FakeRepo(order=dict(_ORDER), active=True)
    _patch_repo(monkeypatch, repo)
    with pytest.raises(HTTPException) as exc:
        _call()
    assert exc.value.status_code == 409
    assert StubYooKassa.calls == 0
    assert repo.reservations == []  # слот не захвачен повторно


def test_success_updates_exactly_one_reservation(monkeypatch) -> None:
    repo = FakeRepo(order=dict(_ORDER), active=False)
    _patch_repo(monkeypatch, repo)
    out = _call()
    assert StubYooKassa.calls == 1
    assert len(repo.reservations) == 1
    assert repo.updated == [
        ("res-1", {"provider_payment_id": "prov-1", "status_value": "pending"})
    ]
    assert out["provider_payment_id"] == "prov-1"


def test_definite_provider_error_marks_failed_and_502(monkeypatch) -> None:
    StubYooKassa.response = {"ok": False, "error": "rejected", "payment_id": None}
    repo = FakeRepo(order=dict(_ORDER), active=False)
    _patch_repo(monkeypatch, repo)
    with pytest.raises(HTTPException) as exc:
        _call()
    assert exc.value.status_code == 502
    assert StubYooKassa.calls == 1
    assert repo.failed_ids == ["res-1"]  # слот освобождён


def test_ambiguous_timeout_keeps_reservation_active(monkeypatch) -> None:
    StubYooKassa.raise_http = True
    repo = FakeRepo(order=dict(_ORDER), active=False)
    _patch_repo(monkeypatch, repo)
    with pytest.raises(HTTPException) as exc:
        _call()
    assert exc.value.status_code == 502
    assert StubYooKassa.calls == 1
    # reservation НЕ помечена failed, provider повторно не вызывался
    assert repo.failed_ids == []
    assert len(repo.reservations) == 1


def test_terminal_failed_allows_new_attempt(monkeypatch) -> None:
    # terminal-статусы не блокируют новый слот: reservation создаётся заново
    repo = FakeRepo(order=dict(_ORDER), active=False)
    _patch_repo(monkeypatch, repo)
    out = _call()
    assert StubYooKassa.calls == 1
    assert out["confirmation_url"]


def test_paid_order_still_400_without_provider(monkeypatch) -> None:
    order = dict(_ORDER)
    order["status"] = "paid"
    repo = FakeRepo(order=order, active=False)
    _patch_repo(monkeypatch, repo)
    with pytest.raises(HTTPException) as exc:
        _call()
    assert exc.value.status_code == 400
    assert StubYooKassa.calls == 0
    assert repo.reservations == []


def test_webhook_does_not_bind_terminal_reservation() -> None:
    rows = [
        {"id": "terminal", "order_id": "o1", "provider_payment_id": None, "status": "failed"},
        {"id": "active", "order_id": "o1", "provider_payment_id": None, "status": "pending"},
    ]

    class FakeQuery:
        def __init__(self, table: "FakePaymentsTable") -> None:
            self.table = table
            self.filters: dict[str, Any] = {}

        def select(self, *_fields: str) -> "FakeQuery":
            return self

        def eq(self, column: str, value: Any) -> "FakeQuery":
            self.filters[column] = value
            return self

        def is_(self, column: str, value: str) -> "FakeQuery":
            self.filters[column] = None
            return self

        def order(self, *_args: Any, **_kwargs: Any) -> "FakeQuery":
            return self

        def limit(self, *_args: Any, **_kwargs: Any) -> "FakeQuery":
            return self

        def execute(self) -> SimpleNamespace:
            data = [
                row for row in self.table.rows
                if all(row.get(column) == value for column, value in self.filters.items())
            ]
            return SimpleNamespace(data=data)

    class FakeUpdate:
        def __init__(self, table: "FakePaymentsTable", fields: dict[str, Any]) -> None:
            self.table = table
            self.fields = fields
            self.payment_id: str | None = None

        def eq(self, _column: str, value: str) -> "FakeUpdate":
            self.payment_id = value
            return self

        def execute(self) -> SimpleNamespace:
            for row in self.table.rows:
                if row["id"] == self.payment_id:
                    row.update(self.fields)
                    return SimpleNamespace(data=[row])
            return SimpleNamespace(data=[])

    class FakePaymentsTable:
        def __init__(self) -> None:
            self.rows = [dict(row) for row in rows]

        def select(self, *_fields: str) -> FakeQuery:
            return FakeQuery(self)

        def update(self, fields: dict[str, Any]) -> FakeUpdate:
            return FakeUpdate(self, fields)

    table = FakePaymentsTable()
    repository = object.__new__(CaseRepository)
    repository.client = SimpleNamespace(table=lambda _name: table)

    result = repository._bind_reservation(
        order_id="o1",
        provider_payment_id="provider-1",
        status_value="succeeded",
    )

    assert result is not None
    assert result["id"] == "active"
    assert table.rows[0]["provider_payment_id"] is None
    assert table.rows[1]["provider_payment_id"] == "provider-1"
