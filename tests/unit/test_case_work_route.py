"""SoT маршрута «Работа с делом»."""

from __future__ import annotations

from sfrfr.services.case_work_route import build_case_work_route


def test_no_docs_offers_request_from_client() -> None:
    route = build_case_work_route(documents=[], document_check=None)
    assert route["current_step_id"] == "docs_check"
    assert route["steps"][0]["status"] == "blocked"
    action = route["primary_action"]
    assert action is not None
    assert action["id"] == "request_docs_from_client"
    assert action["label"] == "Запросить документы"
    assert route["auto_send_appeal"] is False


def test_primary_is_docs_check_when_missing() -> None:
    route = build_case_work_route(
        documents=[{"id": "d1"}],
        document_check=None,
    )
    action = route["primary_action"]
    assert action is not None
    assert action["id"] == "request_docs_check"
    assert action["path_suffix"] == "request-review"


_DONE_CHECK = {
    "status": "completed",
    "stale": False,
    "result": {
        "originals_available": 1,
        "text_extracted": 1,
        "needs_recognition": 0,
        "needs_manual_review": 0,
        "missing_for_task": [],
        "next_action": "ok",
    },
}


def test_completed_check_with_pipeline_advances_to_appeal() -> None:
    route = build_case_work_route(
        documents=[{"id": "d1"}],
        document_check=_DONE_CHECK,
        findings=[],
        draft=None,
        pipeline_ran=True,
    )
    assert route["steps"][0]["status"] == "done"
    assert route["steps"][1]["status"] == "done"
    assert route["current_step_id"] == "appeal_draft"
    assert route["primary_action"]["id"] == "open_appeals_stage"


def test_no_pipeline_means_manual_facts_review_not_fake_done() -> None:
    route = build_case_work_route(
        documents=[{"id": "d1"}], document_check=_DONE_CHECK, findings=[], draft=None
    )
    facts = route["steps"][1]
    assert facts["status"] == "current"
    assert route["primary_action"]["id"] == "record_facts_review"
    assert "без явных блокеров" not in (facts["result_summary"] or "")


def test_recorded_facts_review_unlocks_appeal() -> None:
    route = build_case_work_route(
        documents=[{"id": "d1"}],
        document_check=_DONE_CHECK,
        findings=[],
        draft=None,
        facts_review="discrepancies",
    )
    assert route["steps"][1]["status"] == "done"
    assert "расхождения есть" in route["steps"][1]["result_summary"].lower()
    assert route["current_step_id"] == "appeal_draft"
    assert route["primary_action"]["id"] == "open_appeals_stage"


def test_unreadable_extra_file_does_not_block_when_kit_complete() -> None:
    route = build_case_work_route(
        documents=[{"id": "d1"}, {"id": "d2"}, {"id": "d3"}],
        document_check={
            "status": "needs_action",
            "stale": False,
            "result": {
                "originals_available": 3,
                "text_extracted": 2,
                "needs_recognition": 1,
                "needs_manual_review": 0,
                "missing_for_task": [],
                "unreadable_files": ["photo.png"],
                "unreadable_core": 0,
                "next_action": "Запустите распознавание для 1 файл(ов)",
            },
        },
    )
    docs = route["steps"][0]
    assert docs["status"] == "done"
    assert "photo.png" in docs["result_summary"]
    assert route["current_step_id"] == "facts_review"


def test_needs_action_keeps_specialist_on_docs() -> None:
    route = build_case_work_route(
        documents=[{"id": "d1"}, {"id": "d2"}],
        document_check={
            "status": "needs_action",
            "stale": False,
            "result": {
                "originals_available": 2,
                "text_extracted": 1,
                "needs_recognition": 0,
                "needs_manual_review": 2,
                "missing_for_task": [],
                "next_action": "Проверьте текст двух документов",
            },
        },
    )
    assert route["current_step_id"] == "docs_check"
    assert route["steps"][0]["needs_specialist"] is True
    assert "двух" in (route["blocker_reason"] or "") or "2" in (
        route["steps"][0]["result_summary"] or ""
    )
    action = route["primary_action"]
    assert action is not None
    assert action["id"] == "request_docs_check"
    assert action["label"] == "Проверить документы"
