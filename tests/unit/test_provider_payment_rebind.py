"""Webhook succeeded B при bound pending A (тот же order) — перепривязка.

Регресс smoke 1421177: _bind_reservation только при provider_payment_id IS NULL
игнорировал succeeded с другим id → HTTP 200 ignored, order не paid.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from fastapi import HTTPException
from postgrest.exceptions import APIError

from sfrfr.db.case_repository import CaseRepository

ORDER_ID = "08edeb1b-b44f-4cb2-8c5f-9885dad18100"
CASE_ID = "76e662a1-d8ce-4edf-b7f3-365685e841f3"
PAY_A = "326d0f50-000f-5001-9000-11750a6a9499"
PAY_B = "326d0ff7-000f-5001-8000-1c3bad0e109c"


class _MemQuery:
    def __init__(self, client: _MemClient, name: str) -> None:
        self.client = client
        self.name = name
        self._filters: list[tuple[str, Any]] = []
        self._null_cols: list[str] = []
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None
        self._update: dict[str, Any] | None = None
        self._insert: dict[str, Any] | None = None
        self._select = "*"

    def select(self, _cols: str = "*") -> _MemQuery:
        self._select = _cols
        return self

    def eq(self, col: str, val: Any) -> _MemQuery:
        self._filters.append((col, val))
        return self

    def is_(self, col: str, val: str) -> _MemQuery:
        if str(val).lower() == "null":
            self._null_cols.append(col)
        return self

    def order(self, col: str, desc: bool = False) -> _MemQuery:
        self._order = (col, desc)
        return self

    def limit(self, n: int) -> _MemQuery:
        self._limit = n
        return self

    def update(self, payload: dict[str, Any]) -> _MemQuery:
        self._update = dict(payload)
        return self

    def insert(self, payload: dict[str, Any]) -> _MemQuery:
        self._insert = dict(payload)
        return self

    def _match(self, row: dict[str, Any]) -> bool:
        for col, val in self._filters:
            if row.get(col) != val:
                return False
        for col in self._null_cols:
            if row.get(col) is not None:
                return False
        return True

    def _with_orders(self, row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        if "orders" in self._select or "orders(" in self._select:
            order = next(
                (o for o in self.client.tables.get("orders", []) if o["id"] == row.get("order_id")),
                None,
            )
            if order:
                out["orders"] = {
                    "id": order["id"],
                    "case_id": order.get("case_id"),
                    "status": order.get("status"),
                    "package_code": order.get("package_code"),
                }
        return out

    def execute(self) -> SimpleNamespace:
        rows = list(self.client.tables.get(self.name, []))

        if self._insert is not None:
            if self.name == "payments":
                active = [
                    r
                    for r in rows
                    if r.get("order_id") == self._insert.get("order_id")
                    and str(r.get("status") or "").lower()
                    not in CaseRepository._TERMINAL_PAYMENT_STATUSES
                ]
                if active:
                    raise APIError(
                        {
                            "message": "duplicate key",
                            "code": "23505",
                            "hint": None,
                            "details": None,
                        }
                    )
            row = {"id": f"ins-{len(rows) + 1}", **self._insert}
            self.client.tables.setdefault(self.name, []).append(row)
            return SimpleNamespace(data=[dict(row)])

        matched = [r for r in rows if self._match(r)]
        if self._order:
            col, desc = self._order
            matched.sort(key=lambda r: str(r.get(col) or ""), reverse=desc)
        if self._limit is not None:
            matched = matched[: self._limit]

        if self._update is not None:
            updated: list[dict[str, Any]] = []
            for row in matched:
                row.update(self._update)
                updated.append(dict(row))
            return SimpleNamespace(data=updated)

        return SimpleNamespace(data=[self._with_orders(r) for r in matched])


class _MemClient:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {
            "orders": [],
            "payments": [],
            "cases": [],
            "access_audit": [],
        }

    def table(self, name: str) -> _MemQuery:
        return _MemQuery(self, name)


def _repo(client: _MemClient) -> CaseRepository:
    repo = CaseRepository.__new__(CaseRepository)
    repo.client = client
    return repo


def _seed_pending_a(client: _MemClient) -> None:
    client.tables["orders"] = [
        {
            "id": ORDER_ID,
            "case_id": CASE_ID,
            "status": "pending",
            "package_code": "DIAG",
        }
    ]
    client.tables["cases"] = [{"id": CASE_ID, "b2c_status": "lead"}]
    client.tables["payments"] = [
        {
            "id": "pay-row-1",
            "order_id": ORDER_ID,
            "provider": "yookassa",
            "provider_payment_id": PAY_A,
            "status": "pending",
        }
    ]


def test_succeeded_b_rebinds_stale_pending_a() -> None:
    """Bound pending A + webhook succeeded B (тот же order) → paid, id=B."""
    client = _MemClient()
    _seed_pending_a(client)
    repo = _repo(client)

    out = repo.apply_provider_payment(
        provider_payment_id=PAY_B,
        status_value="succeeded",
        order_id=ORDER_ID,
        paid=True,
        case_id=CASE_ID,
        package_code="DIAG",
    )

    assert out["newly_paid"] is True
    assert out["provider_payment_id"] == PAY_B
    pay = client.tables["payments"][0]
    assert pay["provider_payment_id"] == PAY_B
    assert pay["status"] == "succeeded"
    assert client.tables["orders"][0]["status"] == "paid"
    assert client.tables["cases"][0]["b2c_status"] == "diagnostic_paid"


def test_already_paid_same_id_is_idempotent() -> None:
    client = _MemClient()
    _seed_pending_a(client)
    client.tables["payments"][0]["provider_payment_id"] = PAY_B
    client.tables["payments"][0]["status"] = "succeeded"
    client.tables["orders"][0]["status"] = "paid"
    repo = _repo(client)

    out = repo.apply_provider_payment(
        provider_payment_id=PAY_B,
        status_value="succeeded",
        order_id=ORDER_ID,
        paid=True,
        case_id=CASE_ID,
    )

    assert out["newly_paid"] is False
    assert client.tables["payments"][0]["provider_payment_id"] == PAY_B


def test_already_paid_a_does_not_rebind_to_b() -> None:
    """Paid A не перезаписываем на B — слот терминальный, rebind не трогает."""
    client = _MemClient()
    _seed_pending_a(client)
    client.tables["payments"][0]["status"] = "succeeded"
    client.tables["orders"][0]["status"] = "paid"
    repo = _repo(client)

    try:
        repo.apply_provider_payment(
            provider_payment_id=PAY_B,
            status_value="succeeded",
            order_id=ORDER_ID,
            paid=True,
            case_id=CASE_ID,
        )
    except HTTPException as exc:
        assert exc.status_code == 404

    paid_a = next(p for p in client.tables["payments"] if p["id"] == "pay-row-1")
    assert paid_a["provider_payment_id"] == PAY_A
    assert paid_a["status"] == "succeeded"
