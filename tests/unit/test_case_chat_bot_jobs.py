"""Очередь bot_reply: дедуп, retry, fallback специалисту."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfrfr.services.case_chat_bot_jobs import (
    HANDOFF_TEXT,
    enqueue_bot_reply_job,
    expire_stale_bot_jobs,
    is_retryable_error,
    new_correlation_id,
    process_bot_reply_jobs,
)


def test_correlation_id_is_uuid() -> None:
    cid = new_correlation_id()
    assert len(cid) == 36
    assert cid.count("-") == 4


def test_retryable_only_transient() -> None:
    assert is_retryable_error(RuntimeError("HTTP 429 rate limit"))
    assert is_retryable_error(TimeoutError("timed out"))
    assert not is_retryable_error(RuntimeError("401 unauthorized"))
    assert not is_retryable_error(ValueError("validation failed"))


@patch("sfrfr.db.session.get_supabase_client")
def test_enqueue_returns_existing_job(mock_sb: MagicMock) -> None:
    table = MagicMock()
    mock_sb.return_value.table.return_value = table
    table.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"id": "job-1", "status": "queued"}
    ]
    job_id = enqueue_bot_reply_job(
        case_id="00000000-0000-4000-8000-000000000001",
        message_id="00000000-0000-4000-8000-000000000002",
        correlation_id="corr-1",
    )
    assert job_id == "job-1"
    table.insert.assert_not_called()


@patch("sfrfr.db.session.get_supabase_client")
def test_enqueue_inserts_when_new(mock_sb: MagicMock) -> None:
    table = MagicMock()
    mock_sb.return_value.table.return_value = table
    table.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    table.insert.return_value.execute.return_value.data = [{"id": "job-new"}]
    job_id = enqueue_bot_reply_job(
        case_id="00000000-0000-4000-8000-000000000001",
        message_id="00000000-0000-4000-8000-000000000002",
        correlation_id="corr-2",
    )
    assert job_id == "job-new"
    table.insert.assert_called_once()
    payload = table.insert.call_args.args[0]
    assert payload["correlation_id"] == "corr-2"
    assert payload["status"] == "queued"


@patch("sfrfr.services.case_chat_bot_jobs.CaseRepository", create=True)
@patch("sfrfr.services.case_chat_bot.auto_reply_to_client_message")
@patch("sfrfr.db.case_repository.CaseRepository")
@patch("sfrfr.db.session.get_supabase_client")
def test_worker_completes_one_reply(
    mock_sb: MagicMock,
    mock_repo_cls: MagicMock,
    mock_reply: MagicMock,
    _unused: MagicMock,
) -> None:
    table = MagicMock()
    mock_sb.return_value.table.return_value = table
    due = table.select.return_value.in_.return_value.lte.return_value.order.return_value.limit
    due.return_value.execute.return_value.data = [
        {
            "id": "job-1",
            "case_id": "00000000-0000-4000-8000-000000000001",
            "message_id": "00000000-0000-4000-8000-000000000002",
            "correlation_id": "corr",
            "attempt_count": 0,
            "status": "queued",
        }
    ]
    table.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"body": "Когда будет результат проверки?", "author_kind": "client"}
    ]
    mock_repo_cls.return_value.get_case_row.return_value = {
        "id": "00000000-0000-4000-8000-000000000001",
        "clients": {},
    }
    mock_reply.return_value = {"id": "bot-msg"}
    n = process_bot_reply_jobs(limit=1)
    assert n == 1
    mock_reply.assert_called_once()


@patch("sfrfr.services.case_chat_bot._append_bot_reply")
@patch("sfrfr.db.case_repository.CaseRepository")
@patch("sfrfr.db.session.get_supabase_client")
def test_stale_job_handoffs_to_specialist(
    mock_sb: MagicMock,
    mock_repo_cls: MagicMock,
    mock_append: MagicMock,
) -> None:
    table = MagicMock()
    mock_sb.return_value.table.return_value = table
    stale = table.select.return_value.in_.return_value.lt.return_value.limit
    stale.return_value.execute.return_value.data = [
        {
            "id": "job-stale",
            "case_id": "00000000-0000-4000-8000-000000000001",
            "correlation_id": "corr",
            "attempt_count": 1,
            "status": "processing",
        }
    ]
    mock_repo_cls.return_value.get_case_row.return_value = {
        "id": "00000000-0000-4000-8000-000000000001"
    }
    mock_append.return_value = {"id": "handoff-msg"}
    n = expire_stale_bot_jobs()
    assert n == 1
    assert mock_append.call_args.kwargs["reply"] == HANDOFF_TEXT
    assert "специалисту" in HANDOFF_TEXT
    assert "СНИЛС" not in HANDOFF_TEXT
