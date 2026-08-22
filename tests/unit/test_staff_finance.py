"""Очередь финансов без формулы ЕДВ."""

from datetime import UTC, datetime, timedelta

from sfrfr.services.staff_finance import build_finance_snapshot, finance_status


def _order(**kwargs: object) -> dict:
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "case_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "package_code": "DIAG",
        "amount_rub": 3000,
        "status": "pending",
        "created_at": "2026-08-20T10:00:00+00:00",
        "payments": [],
    }
    base.update(kwargs)
    return base


def _case(**kwargs: object) -> dict:
    base = {
        "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "b2c_status": "consent_accepted",
        "pipeline_status": "intake",
        "clients": {"full_name": "Сергей", "max_user_id": "1"},
    }
    base.update(kwargs)
    return base


def test_pending_with_past_due_is_overdue() -> None:
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    status = finance_status(
        _order(due_at="2026-08-20T12:00:00+00:00", invoice_status="pending_payment"),
        now=now,
    )
    assert status == "overdue"


def test_paid_stays_paid() -> None:
    assert finance_status(_order(status="paid", invoice_status="pending_payment")) == "paid"


def test_snapshot_hides_test_and_has_no_edv_formula() -> None:
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    due = (now + timedelta(days=1)).isoformat()
    live = _order(id="1", case_id="c1", status="pending", due_at=due)
    test_order = _order(id="2", case_id="c2", status="pending")
    snap = build_finance_snapshot(
        orders=[live, test_order],
        cases=[
            _case(id="c1", clients={"full_name": "Сергей"}),
            _case(id="c2", clients={"full_name": "Тест Клиент AMO"}),
        ],
        now=now,
    )
    assert "formula" not in snap
    assert "ЕДВ" not in snap["disclaimer"]
    assert "прибавк" not in snap["disclaimer"].lower()
    assert snap["kpis"]["payable"]["count"] == 1
    assert snap["orders"][0]["client_name"] == "Сергей"
    assert all("10%" not in (row.get("service_label") or "") for row in snap["orders"])
    assert snap["tariffs"][0]["amount_rub"] == 3000


def test_admin_finance_endpoint_has_no_formula(monkeypatch) -> None:
    from sfrfr.api.routes import admin_portal
    from sfrfr.security.auth import Principal, StaffRole

    class Repo:
        def list_cases(self, _principal):
            return [_case()]

        def list_all_orders(self):
            return [_order()]

    monkeypatch.setattr(admin_portal, "_repo", lambda: Repo())
    principal = Principal(user_id="admin", email="a@x", role=StaffRole.ADMIN)
    out = admin_portal.admin_finance(
        queue=None,
        q=None,
        package_code=None,
        period=None,
        include_test=False,
        principal=principal,
    )
    assert "formula" not in out
    assert "10%" not in out["disclaimer"]
    assert out["can_manage"] is True
