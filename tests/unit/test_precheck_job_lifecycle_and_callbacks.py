"""Job reclaim, empty periods, precheck:* callbacks, offer gates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from sfrfr.services.precheck_period_sources import (
    classify_period_source_state,
    periods_for_precheck,
)
from sfrfr.services.primary_doc_precheck import run_primary_precheck
from sfrfr.services.primary_doc_precheck_callbacks import (
    CALLBACK_CONTRACTS,
    handle_precheck_callback,
    parse_precheck_callback,
)
from sfrfr.services.staff_document_check_lifecycle import (
    notify_already_recorded,
    reclaim_stale_running_jobs,
    result_already_finalized,
)


def test_callback_contracts_cover_min_actions() -> None:
    for key in (
        "summary",
        "explain",
        "need_docs",
        "upload",
        "offer_info",
        "order",
        "decline",
        "ask_staff",
        "status",
    ):
        assert key in CALLBACK_CONTRACTS


def test_parse_precheck_callback() -> None:
    assert parse_precheck_callback("precheck:summary") == "summary"
    assert parse_precheck_callback("other") is None


def test_empty_periods_not_no_discrepancies() -> None:
    res = run_primary_precheck(ils_periods=[], labor_periods=[], kit_missing=["ils"])
    assert res.outcome.value != "no_discrepancies_found"


def test_period_source_states() -> None:
    assert (
        classify_period_source_state(
            has_documents=False, ils=[], labor=[], extract_attempted=False, extract_error=None
        )
        == "documents_missing"
    )
    assert (
        classify_period_source_state(
            has_documents=True,
            ils=[],
            labor=[],
            extract_attempted=True,
            extract_error="Boom",
        )
        == "extract_failed"
    )
    ils, labor, state, err = periods_for_precheck(
        pipeline_row={
            "ils_periods": [
                {"period_id": "p1", "employer": "A", "date_from": "1987-01-01"}
            ]
        },
        analyzed_documents=[],
    )
    assert state == "periods_ready"
    assert ils and not err


def test_result_finalized_and_notify_flags() -> None:
    assert result_already_finalized({"status": "completed", "result": {}})
    assert result_already_finalized(
        {"status": "running", "result": {"primary_precheck": {"outcome": "x"}}}
    )
    assert notify_already_recorded({"client_notify": {"ok": True, "message_id": "m"}})
    assert notify_already_recorded(
        {"result": {"client_notify": {"skipped": True, "reason": "no_max_user"}}}
    )


@patch("sfrfr.db.session.get_supabase_client")
def test_reclaim_stale_running_requeues(mock_sb: MagicMock) -> None:
    client = MagicMock()
    mock_sb.return_value = client
    jobs = MagicMock()
    client.table.return_value = jobs
    old = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    jobs.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {
            "id": "j1",
            "attempts": 1,
            "max_attempts": 3,
            "locked_at": old,
            "status": "running",
        }
    ]
    jobs.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
        {"id": "j1"}
    ]
    out = reclaim_stale_running_jobs(older_than_sec=60)
    assert out["requeued"] == 1
    assert out["failed"] == 0


@patch("sfrfr.services.primary_doc_precheck_callbacks._load_latest_check")
def test_callback_order_does_not_create_invoice(mock_load: MagicMock) -> None:
    mock_load.return_value = {
        "job_id": "chk1",
        "stale": False,
        "result": {
            "primary_precheck": {
                "outcome": "discrepancies_found",
                "comparison_status": "discrepancies_found",
                "client_summary": "Есть различие дат.",
                "recommendation": {
                    "offer_paid_analysis": True,
                    "amount_rub": 3000,
                    "service_scope": "проверка оснований",
                },
                "findings": [
                    {
                        "code": "DATE_DIFFERENCE",
                        "what": "даты",
                        "source_a": "ils:1",
                        "source_b": "labor:2",
                    }
                ],
            }
        },
    }
    res = handle_precheck_callback(
        payload="precheck:order",
        case_id="case-1",
        max_user_id="u1",
    )
    assert res is not None
    assert res.action == "precheck_order_handoff"
    assert "не создаёт" in res.text.casefold() or "не создает" in res.text.casefold()


@patch("sfrfr.services.primary_doc_precheck_callbacks._load_latest_check")
@patch("sfrfr.services.primary_doc_precheck_callbacks._mark_declined")
def test_callback_decline(mock_decline: MagicMock, mock_load: MagicMock) -> None:
    mock_load.return_value = {
        "job_id": "chk1",
        "stale": False,
        "result": {"primary_precheck": {"outcome": "discrepancies_found"}},
    }
    res = handle_precheck_callback(
        payload="precheck:decline", case_id="case-1", max_user_id="u1"
    )
    assert res is not None
    assert res.action == "precheck_declined"
    mock_decline.assert_called_once()


@patch("sfrfr.services.primary_doc_precheck_callbacks._load_latest_check")
@patch("sfrfr.services.primary_doc_precheck_callbacks._mark_ask_staff")
def test_callback_ask_staff_registers(
    mock_ask: MagicMock, mock_load: MagicMock
) -> None:
    mock_ask.return_value = True
    mock_load.return_value = {
        "job_id": "chk1",
        "stale": False,
        "result": {"primary_precheck": {"outcome": "discrepancies_found"}},
    }
    res = handle_precheck_callback(
        payload="precheck:ask_staff", case_id="case-1", max_user_id="u1"
    )
    assert res is not None
    assert res.action == "precheck_ask_staff"
    assert res.detail == "registered"
    mock_ask.assert_called_once_with("case-1", "u1")
    assert "подключён" not in res.text.casefold() or "только после" in res.text.casefold()


def test_outcome_examples_discrepancy_none_insufficient() -> None:
    with_diff = run_primary_precheck(
        ils_periods=[
            {
                "period_id": "i1",
                "employer": "ООО А",
                "date_from": "1990-01-01",
                "date_to": "1995-01-01",
            }
        ],
        labor_periods=[
            {
                "period_id": "l1",
                "employer": "ООО А",
                "date_from": "1990-01-01",
                "date_to": "1994-06-01",
            }
        ],
    )
    assert with_diff.outcome.value == "discrepancies_found"
    assert with_diff.findings

    no_diff = run_primary_precheck(
        ils_periods=[
            {
                "period_id": "i1",
                "employer": "ООО А",
                "date_from": "1990-01-01",
                "date_to": "1995-01-01",
            }
        ],
        labor_periods=[
            {
                "period_id": "l1",
                "employer": "ООО А",
                "date_from": "1990-01-01",
                "date_to": "1995-01-01",
            }
        ],
    )
    assert no_diff.outcome.value == "no_discrepancies_found"
    assert not no_diff.recommendation.offer_paid_analysis

    missing = run_primary_precheck(
        ils_periods=[], labor_periods=[], kit_missing=["ils", "labor"]
    )
    assert missing.outcome.value == "insufficient_documents"
    assert not missing.recommendation.offer_paid_analysis


@patch("sfrfr.services.staff_document_check._enqueue_notify_once")
@patch("sfrfr.db.session.get_supabase_client")
def test_finalized_job_retries_missing_notify_once(
    mock_sb: MagicMock, mock_enqueue: MagicMock
) -> None:
    """Результат сохранён, notify нет → повтор process догоняет notify, не пересчёт."""
    from sfrfr.services.staff_document_check import process_staff_document_check_job

    client = MagicMock()
    mock_sb.return_value = client
    jobs = MagicMock()
    client.table.return_value = jobs
    jobs.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {
            "id": "job-done",
            "case_id": "case-1",
            "status": "completed",
            "result": {
                "primary_precheck": {
                    "outcome": "discrepancies_found",
                    "client_summary": "есть различие",
                }
            },
        }
    ]
    mock_enqueue.return_value = {"ok": True, "message_id": "m1"}
    jobs.update.return_value.eq.return_value.execute.return_value.data = [{"id": "job-done"}]
    out = process_staff_document_check_job("job-done")
    mock_enqueue.assert_called_once()
    assert (out.get("result") or {}).get("client_notify", {}).get("message_id") == "m1"
    # второй вызов с уже записанным notify — без повторного enqueue
    jobs.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        out
    ]
    mock_enqueue.reset_mock()
    process_staff_document_check_job("job-done")
    mock_enqueue.assert_not_called()


@patch("sfrfr.db.session.get_supabase_client")
def test_reclaim_exhausted_marks_failed(mock_sb: MagicMock) -> None:
    """После «перезапуска» процесса: stale running с исчерпанными attempts → failed."""
    client = MagicMock()
    mock_sb.return_value = client
    jobs = MagicMock()
    client.table.return_value = jobs
    old = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    jobs.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {
            "id": "j-ex",
            "attempts": 3,
            "max_attempts": 3,
            "locked_at": old,
            "status": "running",
        }
    ]
    jobs.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
        {"id": "j-ex"}
    ]
    out = reclaim_stale_running_jobs(older_than_sec=60)
    assert out["failed"] == 1
    assert out["requeued"] == 0


@patch("sfrfr.services.primary_doc_precheck_callbacks._load_latest_check")
def test_stale_callback_shows_current(mock_load: MagicMock) -> None:
    mock_load.return_value = {
        "job_id": "chk-new",
        "stale": False,
        "result": {
            "primary_precheck": {
                "outcome": "no_discrepancies_found",
                "client_summary": "Актуально ок.",
                "recommendation": {"offer_paid_analysis": False},
            }
        },
    }
    res = handle_precheck_callback(
        payload="precheck:summary",
        case_id="case-1",
        max_user_id="u1",
        requested_check_id="chk-old",
    )
    assert res is not None
    assert res.action == "stale_show_current"
    assert "обновил" in res.text.casefold() or "актуальн" in res.text.casefold()
