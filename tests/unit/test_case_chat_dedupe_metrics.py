"""client_message_id, dedupe bot reply, Prometheus /metrics."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from sfrfr.api import create_app
from sfrfr.services.case_chat_delivery import (
    find_bot_reply_to_message_id,
    find_message_by_client_message_id,
)


def test_find_message_by_client_message_id_returns_row() -> None:
    with patch("sfrfr.db.session.get_supabase_client") as mock_sb:
        table = MagicMock()
        mock_sb.return_value.table.return_value = table
        chain = table.select.return_value.eq.return_value.eq.return_value.limit
        chain.return_value.execute.return_value.data = [{"id": "msg-1", "body": "hi"}]
        row = find_message_by_client_message_id("case-1", "client-uuid")
    assert row is not None
    assert row["id"] == "msg-1"


def test_find_bot_reply_to_message_id_returns_system_row() -> None:
    with patch("sfrfr.db.session.get_supabase_client") as mock_sb:
        table = MagicMock()
        mock_sb.return_value.table.return_value = table
        chain = table.select.return_value.eq.return_value.eq.return_value.limit
        chain.return_value.execute.return_value.data = [{"id": "bot-1", "author_kind": "system"}]
        row = find_bot_reply_to_message_id("client-msg-1")
    assert row is not None
    assert row["id"] == "bot-1"


@patch("sfrfr.integrations.max.case_chat_log._insert_case_message")
@patch("sfrfr.services.case_chat_delivery.find_bot_reply_to_message_id")
def test_append_case_chat_message_bot_dedupe(mock_find: MagicMock, mock_insert: MagicMock) -> None:
    mock_find.return_value = {"id": "existing-bot", "body": "ok"}
    from sfrfr.integrations.max.case_chat_log import append_case_chat_message

    row = append_case_chat_message(
        case_id="00000000-0000-4000-8000-000000000001",
        author_kind="system",
        body="ответ",
        reply_to_message_id="00000000-0000-4000-8000-000000000002",
    )
    assert row == {"id": "existing-bot", "body": "ok"}
    mock_insert.assert_not_called()


def test_metrics_requires_ops_token() -> None:
    client = TestClient(create_app())
    response = client.get("/metrics")
    assert response.status_code in {401, 503}


@patch("sfrfr.ops.chat_bot_metrics.metrics_payload")
def test_metrics_returns_prometheus_payload(mock_payload: MagicMock) -> None:
    mock_payload.return_value = (b"bot_job_queued_total 1\n", "text/plain; version=0.0.4")
    with patch("sfrfr.api.routes.health.get_settings") as mock_settings:
        mock_settings.return_value.ops_monitor_token = "secret-token"
        client = TestClient(create_app())
        response = client.get("/metrics", headers={"X-Ops-Token": "secret-token"})
    assert response.status_code == 200
    assert b"bot_job_queued_total" in response.content
