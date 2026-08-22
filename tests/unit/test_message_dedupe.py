"""Тесты нормализации и детекции дублей сообщений."""

from datetime import UTC, datetime, timedelta

from sfrfr.services.message_dedupe import (
    count_same_messages,
    find_duplicate_staff_message,
    has_service_consent,
    normalize_message_body,
    required_docs_missing,
)


def test_normalize_collapses_whitespace() -> None:
    assert normalize_message_body("  Привет\n\nмир  ") == "привет мир"


def test_find_duplicate_within_24h() -> None:
    now = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
    rows = [
        {
            "id": "1",
            "author_kind": "staff",
            "body": "Запросите ИЛС",
            "created_at": (now - timedelta(hours=2)).isoformat(),
        },
        {
            "id": "2",
            "author_kind": "client",
            "body": "Запросите ИЛС",
            "created_at": (now - timedelta(hours=1)).isoformat(),
        },
    ]
    found = find_duplicate_staff_message(rows, body="запросите  илс", now=now)
    assert found is not None
    assert found["id"] == "1"


def test_no_duplicate_outside_window() -> None:
    now = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
    rows = [
        {
            "id": "1",
            "author_kind": "staff",
            "body": "Запросите ИЛС",
            "created_at": (now - timedelta(hours=30)).isoformat(),
        }
    ]
    assert find_duplicate_staff_message(rows, body="Запросите ИЛС", now=now) is None


def test_template_code_match() -> None:
    now = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
    rows = [
        {
            "id": "t1",
            "author_kind": "staff",
            "body": "Текст\n\n[template:request_ils]",
            "created_at": (now - timedelta(hours=1)).isoformat(),
        }
    ]
    found = find_duplicate_staff_message(
        rows, body="Другой текст", template_code="request_ils", now=now
    )
    assert found is not None


def test_count_same_48h() -> None:
    now = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
    rows = [
        {
            "author_kind": "staff",
            "body": "Напоминание",
            "created_at": (now - timedelta(hours=h)).isoformat(),
        }
        for h in (1, 10, 20)
    ]
    assert count_same_messages(rows, body="напоминание", within_hours=48, now=now) == 3


def test_required_docs_missing() -> None:
    missing = required_docs_missing({"documents": [], "checklist_items": []})
    assert "выписка ИЛС" in missing
    assert "трудовая / сведения о стаже" in missing


def test_required_docs_ok() -> None:
    case = {
        "documents": [
            {"doc_type": "ils", "storage_path": "a.pdf"},
            {"doc_type": "labor", "storage_path": "b.pdf"},
        ],
        "checklist_items": [],
    }
    assert required_docs_missing(case) == []


def test_service_consent() -> None:
    assert has_service_consent({"b2c_status": "paid"}) is True
    assert has_service_consent({"b2c_status": "lead"}, []) is False
    assert (
        has_service_consent(
            {"b2c_status": "lead"},
            [{"action": "service_consent_recorded"}],
        )
        is True
    )
