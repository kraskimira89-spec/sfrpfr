"""Рабочая очередь: приоритет, SLA и ожидание архива не считаются «без ответа»."""

from datetime import UTC, datetime, timedelta

from sfrfr.services.staff_work_queue import (
    build_dashboard_snapshot,
    build_work_item,
    derive_waiting_on,
)

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


def test_test_name_is_excluded_from_snapshot() -> None:
    from sfrfr.services.staff_work_queue import is_test_case

    case = {
        "id": "t1",
        "pipeline_status": "intake",
        "b2c_status": "lead",
        "is_test": False,
        "created_at": NOW.isoformat(),
        "clients": {"full_name": "Тест Клиент AMO", "preferred_channel": "unset"},
        "checklist_items": [],
        "orders": [],
    }
    assert is_test_case(case) is True
    snap = build_dashboard_snapshot([case], [], now=NOW)
    assert snap["work_queue"] == []
    assert snap["new_leads"] == 0


def test_archive_wait_is_not_staff_sla() -> None:
    case = {
        "id": "c1",
        "pipeline_status": "documents_received",
        "b2c_status": "consent_accepted",
        "waiting_on": "archive",
        "created_at": (NOW - timedelta(days=5)).isoformat(),
        "checklist_items": [{"title": "Архивная справка", "status": "open", "owner": "client"}],
        "clients": {"full_name": "Иванов", "preferred_channel": "max_miniapp"},
    }
    item = build_work_item(case, now=NOW)
    assert item is not None
    assert item["waiting_on"] == "archive"
    assert item["deadline_status"] == "waiting"
    assert item["priority"] != "urgent"


def test_intake_without_reply_is_staff_and_can_be_urgent() -> None:
    case = {
        "id": "c2",
        "pipeline_status": "intake",
        "b2c_status": "lead",
        "created_at": (NOW - timedelta(hours=2)).isoformat(),
        "first_contact_at": (NOW - timedelta(hours=2)).isoformat(),
        "checklist_items": [],
        "clients": {"full_name": "Петров", "preferred_channel": "web_cabinet"},
    }
    assert derive_waiting_on(case) == "staff"
    item = build_work_item(case, now=NOW)
    assert item is not None
    assert item["waiting_on"] == "staff"
    assert item["deadline_status"] == "overdue"
    assert item["priority"] == "urgent"
    assert "Связаться" in item["next_action"] or "документы" in item["next_action"].lower()


def test_snapshot_cards_and_queue_order() -> None:
    overdue = {
        "id": "a",
        "pipeline_status": "intake",
        "b2c_status": "lead",
        "created_at": (NOW - timedelta(hours=3)).isoformat(),
        "clients": {"full_name": "А", "preferred_channel": "unset"},
        "checklist_items": [],
        "orders": [],
    }
    waiting_ils = {
        "id": "b",
        "pipeline_status": "intake",
        "b2c_status": "consent_accepted",
        "waiting_on": "client",
        "next_action": "Запросить выписку ИЛС",
        "created_at": (NOW - timedelta(days=4)).isoformat(),
        "clients": {"full_name": "Б", "preferred_channel": "max_miniapp"},
        "checklist_items": [
            {"title": "Выписка ИЛС", "status": "open", "owner": "client", "item_type": "document"}
        ],
        "orders": [],
    }
    closed = {
        "id": "c",
        "pipeline_status": "completed",
        "b2c_status": "closed",
        "created_at": NOW.isoformat(),
        "clients": {"full_name": "В", "preferred_channel": "unset"},
        "checklist_items": [],
        "orders": [],
    }
    snap = build_dashboard_snapshot(
        [overdue, waiting_ils, closed],
        [{"status": "pending", "amount_rub": 3000, "case_id": "b"}],
        now=NOW,
    )
    assert snap["needs_reply"] == 1
    assert snap["sla_risk"] == 1
    assert snap["waiting_docs"] == 1
    assert snap["doc_status"]["ils_missing"] == 1
    assert snap["payments_pending"] == 1
    assert snap["payments_pending_amount"] == 3000
    assert snap["work_queue"][0]["case_id"] == "a"
    assert all(row["case_id"] != "c" for row in snap["work_queue"])
