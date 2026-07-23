"""Тесты клиентского portal API (хелперы и контракты ТЗ-03)."""

from __future__ import annotations

from sfrfr.api.schemas.portal import ClientCaseDetail
from sfrfr.db.case_repository import CaseRepository


def test_next_client_action_prefers_client_open_item() -> None:
    case = {
        "checklist_items": [
            {"title": "Эксперт сверит ИЛС", "owner": "expert", "status": "open", "sort_order": 1},
            {"title": "Загрузить трудовую", "owner": "client", "status": "open", "sort_order": 2},
            {"title": "Готово", "owner": "client", "status": "done", "sort_order": 0},
        ]
    }
    assert CaseRepository.next_client_action(case) == "Загрузить трудовую"


def test_required_document_items_filters_client_docs() -> None:
    case = {
        "checklist_items": [
            {
                "id": "1",
                "title": "Паспорт",
                "item_type": "document",
                "owner": "client",
                "status": "open",
            },
            {
                "id": "2",
                "title": "Запросить архив",
                "item_type": "action",
                "owner": "client",
                "status": "open",
            },
            {
                "id": "3",
                "title": "Скан паспорта",
                "item_type": "document",
                "owner": "client",
                "status": "done",
            },
        ]
    }
    docs = CaseRepository.required_document_items(case)
    assert len(docs) == 1
    assert docs[0]["title"] == "Паспорт"


def test_client_case_detail_contains_sfr_warning() -> None:
    detail = ClientCaseDetail(
        id="00000000-0000-0000-0000-000000000001",
        pipeline_status="intake",
        b2c_status="lead",
    )
    assert "СФР" in detail.warning
    assert "не гарантирован" in detail.warning
