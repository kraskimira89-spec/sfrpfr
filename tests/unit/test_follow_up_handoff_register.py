"""Handoff ступени 10 создаёт review на ступени 11 (idempotent)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from sfrfr.services.follow_up_record import record_follow_up_control


def test_response_handoff_registers_review() -> None:
    repo = MagicMock()
    repo.get_follow_up_event_by_idempotency.return_value = None
    repo.insert_follow_up_event.side_effect = lambda row: {**row, "id": row["id"]}
    repo.update_next_action.return_value = {"id": "c1"}
    repo.audit.return_value = None

    registered: list[dict[str, Any]] = []

    def _fake_register(
        _repo: Any,
        *,
        case_id: str,
        actor_id: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        registered.append({"case_id": case_id, "actor_id": actor_id, **payload})
        return {"ok": True, "review": {"id": "rev-1", "status": "received"}}

    with patch(
        "sfrfr.services.response_review_record.register_response_review",
        side_effect=_fake_register,
    ):
        out = record_follow_up_control(
            repo,
            case_id="c1",
            actor_id="staff-1",
            payload={
                "kind": "response_handoff",
                "document_id": "doc-99",
                "idempotency_key": "idem-h",
            },
            case_row={"id": "c1"},
        )

    assert out["ok"] is True
    assert out["replayed"] is False
    assert len(registered) == 1
    assert registered[0]["document_id"] == "doc-99"
    assert registered[0]["idempotency_key"] == "handoff:doc-99"
    assert registered[0]["respondent"] == "sfr"
    assert registered[0]["response_kind"] == "decision"


def test_response_handoff_survives_register_error() -> None:
    repo = MagicMock()
    repo.get_follow_up_event_by_idempotency.return_value = None
    repo.insert_follow_up_event.side_effect = lambda row: {**row, "id": row["id"]}
    repo.update_next_action.return_value = {"id": "c1"}
    repo.audit.return_value = None

    with patch(
        "sfrfr.services.response_review_record.register_response_review",
        side_effect=RuntimeError("db down"),
    ):
        out = record_follow_up_control(
            repo,
            case_id="c1",
            actor_id="staff-1",
            payload={
                "kind": "response_handoff",
                "document_id": "doc-1",
                "idempotency_key": "idem-err",
            },
            case_row={"id": "c1"},
        )

    assert out["ok"] is True
