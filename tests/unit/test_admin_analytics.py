"""Обезличенная аналитика admin portal (ТЗ-17)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from sfrfr.api.routes import admin_portal
from sfrfr.security.auth import Principal, StaffRole
from sfrfr.services.admin_analytics import (
    FORBIDDEN_EXPORT_KEYS,
    analytics_export_rows,
    assert_no_forbidden_fields,
    build_admin_analytics,
    case_to_analytics_row,
    classify_topic,
    rows_to_json,
)

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


def _sample_case(**overrides: object) -> dict:
    created = (NOW - timedelta(days=3)).isoformat()
    first_contact = (NOW - timedelta(days=2, hours=20)).isoformat()
    base = {
        "id": "00000000-0000-0000-0000-000000000101",
        "pipeline_status": "intake",
        "b2c_status": "lead",
        "segment": "b2c",
        "region_bucket": "77",
        "problem_type": "не учли стаж",
        "created_at": created,
        "first_contact_at": first_contact,
        "expert_user_id": None,
        "clients": {
            "preferred_channel": "unset",
            "max_user_id": None,
            "user_id": None,
        },
        "checklist_items": [],
        "documents": [],
        "consents": [],
        "orders": [],
        "result_evidence": [],
    }
    base.update(overrides)
    return base


def test_case_to_analytics_row_has_no_forbidden_fields() -> None:
    row = case_to_analytics_row(_sample_case())
    assert_no_forbidden_fields([row])
    assert "full_name" not in row
    assert "phone" not in row
    assert row["preferred_channel"] == "unset"
    assert row["result_band"] in {"unknown", "flat", "confirmed_change"}


def test_classify_topic_uses_people_first_labels() -> None:
    assert classify_topic("не учли стаж") == "Неучтённый период работы"
    assert classify_topic("проверка ils") == "Проверка ИЛС"
    assert classify_topic(None) == "Другая тема"


def test_build_admin_analytics_snapshot_shape() -> None:
    cases = [
        _sample_case(),
        _sample_case(
            id="00000000-0000-0000-0000-000000000102",
            clients={"preferred_channel": "max_miniapp", "max_user_id": "m1", "user_id": None},
            orders=[{"package_code": "DIAG", "status": "paid", "amount_rub": 3000}],
            b2c_status="diagnostic_paid",
        ),
    ]
    orders = [
        {
            "case_id": "00000000-0000-0000-0000-000000000102",
            "package_code": "DIAG",
            "status": "paid",
            "amount_rub": 3000,
        },
    ]
    snap = build_admin_analytics(cases=cases, orders=orders, now=NOW, include_finance=True)
    assert snap["kpi"]["total_cases"] == 2
    assert snap["kpi"]["no_channel"] == 1
    assert len(snap["funnel"]) == 9
    assert snap["funnel"][0]["label"] == "Заявка"
    assert snap["channels"][0]["label"] in {"MAX mini-app", "Канал не определён"}
    assert snap["finance"] is not None
    assert snap["finance"]["paid_diagnostics"] == 1
    assert "rows" not in snap


def test_export_rows_json_has_no_forbidden_keys() -> None:
    cases = [_sample_case(), _sample_case(id="00000000-0000-0000-0000-000000000102")]
    rows = analytics_export_rows(cases=cases, orders=[], now=NOW)
    payload = json.loads(rows_to_json(rows))
    assert isinstance(payload, list)
    for row in payload:
        for key in row:
            assert key not in FORBIDDEN_EXPORT_KEYS


def test_admin_analytics_endpoint_rejects_operator() -> None:
    principal = Principal(user_id="op", email="op@x", role=StaffRole.OPERATOR)
    with pytest.raises(HTTPException) as exc:
        admin_portal.admin_analytics(principal=principal)
    assert exc.value.status_code == 403


def test_admin_analytics_endpoint_expert_without_finance(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = MagicMock()
    repo.list_analytics_cases.return_value = [_sample_case()]
    repo.list_all_orders.return_value = []
    monkeypatch.setattr(admin_portal, "_repo", lambda: repo)

    expert = Principal(user_id="ex", email="ex@x", role=StaffRole.EXPERT)
    payload = admin_portal.admin_analytics(
        principal=expert,
        period="30d",
        date_from=None,
        date_to=None,
        channel=None,
        package_code=None,
        pipeline_status=None,
    )
    assert payload["kpi"]["total_cases"] == 1
    assert payload["finance"] is None


def test_admin_analytics_endpoint_admin_includes_finance(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = MagicMock()
    repo.list_analytics_cases.return_value = [
        _sample_case(
            orders=[{"package_code": "DIAG", "status": "paid", "amount_rub": 3000}],
            b2c_status="diagnostic_paid",
        )
    ]
    repo.list_all_orders.return_value = [
        {
            "case_id": "00000000-0000-0000-0000-000000000101",
            "package_code": "DIAG",
            "status": "paid",
            "amount_rub": 3000,
        },
    ]
    monkeypatch.setattr(admin_portal, "_repo", lambda: repo)

    admin = Principal(user_id="ad", email="ad@x", role=StaffRole.ADMIN)
    payload = admin_portal.admin_analytics(
        principal=admin,
        period="30d",
        date_from=None,
        date_to=None,
        channel=None,
        package_code=None,
        pipeline_status=None,
    )
    assert payload["finance"] is not None
    assert payload["finance"]["paid_diagnostics"] == 1


def test_admin_analytics_export_logs_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = MagicMock()
    repo.list_analytics_cases.return_value = [_sample_case()]
    repo.list_all_orders.return_value = []
    monkeypatch.setattr(admin_portal, "_repo", lambda: repo)

    expert = Principal(user_id="ex", email="ex@x", role=StaffRole.EXPERT)
    response = admin_portal.admin_analytics_export(
        principal=expert,
        format="json",
        period="7d",
        date_from=None,
        date_to=None,
        channel=None,
        package_code=None,
        pipeline_status=None,
    )
    assert response.media_type == "application/json; charset=utf-8"
    repo.audit.assert_called_once()
    assert "analytics_export:json:7d" in repo.audit.call_args[0][2]


def test_list_analytics_cases_does_not_embed_orders_paid_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from sfrfr.db.case_repository import CaseRepository

    client = MagicMock()
    select_chain = client.table.return_value.select.return_value
    select_chain.order.return_value.execute.return_value = SimpleNamespace(data=[])
    monkeypatch.setattr("sfrfr.db.case_repository.get_supabase_client", lambda: client)

    repo = CaseRepository()
    repo.list_analytics_cases(Principal(user_id="ad", email="ad@x", role=StaffRole.ADMIN))
    select_sql = str(client.table.return_value.select.call_args[0][0])
    assert "paid_at" not in select_sql
    assert "orders(package_code, status, amount_rub, created_at)" in select_sql
