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


def test_channel_conflict_prefer_max_without_link() -> None:
    case = {
        "id": "cf1",
        "pipeline_status": "intake",
        "b2c_status": "lead",
        "created_at": NOW.isoformat(),
        "checklist_items": [],
        "clients": {
            "full_name": "Сидоров",
            "preferred_channel": "max_miniapp",
            "max_user_id": None,
            "user_id": "auth-1",
        },
    }
    item = build_work_item(case, now=NOW)
    assert item is not None
    assert item["channel_conflict"] is True
    assert item["conflict_kind"] == "prefer_max_unlinked"
    assert item["max_linked"] is False
    assert item["web_linked"] is True
    assert "MAX" in (item["conflict_detail"] or "")


def test_channel_conflict_prefer_web_without_link() -> None:
    case = {
        "id": "cf2",
        "pipeline_status": "documents_received",
        "b2c_status": "consent_accepted",
        "waiting_on": "client",
        "created_at": NOW.isoformat(),
        "checklist_items": [],
        "clients": {
            "full_name": "Козлова",
            "preferred_channel": "web_cabinet",
            "max_user_id": "12345",
            "user_id": None,
        },
    }
    item = build_work_item(case, now=NOW)
    assert item is not None
    assert item["channel_conflict"] is True
    assert item["conflict_kind"] == "prefer_web_unlinked"
    assert item["max_linked"] is True
    assert item["web_linked"] is False


def test_no_conflict_when_preferred_channel_linked() -> None:
    case = {
        "id": "cf3",
        "pipeline_status": "intake",
        "b2c_status": "lead",
        "created_at": NOW.isoformat(),
        "checklist_items": [],
        "clients": {
            "full_name": "Ок",
            "preferred_channel": "max_miniapp",
            "max_user_id": "99",
            "user_id": None,
        },
    }
    item = build_work_item(case, now=NOW)
    assert item is not None
    assert item["channel_conflict"] is False
    assert item["conflict_kind"] is None
    assert item["max_linked"] is True


def test_conflicts_queue_filter_uses_channel_conflict_not_any_channel() -> None:
    """Контракт UI: conflicts = channel_conflict, не «канал != unset»."""
    conflict = build_work_item(
        {
            "id": "f1",
            "pipeline_status": "intake",
            "b2c_status": "lead",
            "created_at": NOW.isoformat(),
            "checklist_items": [],
            "clients": {
                "full_name": "Конфликт",
                "preferred_channel": "max_miniapp",
                "max_user_id": None,
                "user_id": "u1",
            },
        },
        now=NOW,
    )
    linked = build_work_item(
        {
            "id": "f2",
            "pipeline_status": "intake",
            "b2c_status": "lead",
            "created_at": NOW.isoformat(),
            "checklist_items": [],
            "clients": {
                "full_name": "Ок",
                "preferred_channel": "max_miniapp",
                "max_user_id": "42",
                "user_id": None,
            },
        },
        now=NOW,
    )
    assert conflict is not None and linked is not None
    items = [conflict, linked]
    broken = [i for i in items if i["channel"] != "unset"]
    correct = [i for i in items if i["channel_conflict"]]
    assert len(broken) == 2
    assert [i["case_id"] for i in correct] == ["f1"]
