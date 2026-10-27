"""Ступень 10: внутренняя контрольная дата (не срок СФР)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from sfrfr.services.follow_up_control import (
    CLIENT_REPORTED_RESPONSE_NOTE,
    FollowUpControlError,
    derive_ui_state,
    validate_control_payload,
)


def test_need_assign_when_no_date() -> None:
    assert (
        derive_ui_state(
            submission_confirmed=True,
            follow_up_completed=False,
            response_received=False,
            has_control_at=False,
            control_at=None,
        )
        == "need_assign"
    )


def test_due_today_and_overdue_in_yekaterinburg() -> None:
    # 2026-10-27 20:00 UTC = 2026-10-28 01:00 +05 → calendar 28th
    now = datetime(2026, 10, 27, 20, 0, tzinfo=UTC)
    assert (
        derive_ui_state(
            submission_confirmed=True,
            follow_up_completed=False,
            response_received=False,
            has_control_at=True,
            control_at="2026-10-28T00:00:00+05:00",
            now=now,
        )
        == "due_today"
    )
    assert (
        derive_ui_state(
            submission_confirmed=True,
            follow_up_completed=False,
            response_received=False,
            has_control_at=True,
            control_at="2026-10-20T12:00:00+05:00",
            now=now,
        )
        == "overdue_internal"
    )


def test_awaiting_future_date() -> None:
    now = datetime(2026, 10, 27, 10, 0, tzinfo=UTC)
    assert (
        derive_ui_state(
            submission_confirmed=True,
            follow_up_completed=False,
            response_received=False,
            has_control_at=True,
            control_at="2026-11-01T12:00:00+05:00",
            now=now,
        )
        == "awaiting_date"
    )


def test_done_when_response_received() -> None:
    assert (
        derive_ui_state(
            submission_confirmed=True,
            follow_up_completed=False,
            response_received=True,
            has_control_at=True,
            control_at="2026-10-01T12:00:00+05:00",
        )
        == "done"
    )


def test_reschedule_requires_reason() -> None:
    with pytest.raises(FollowUpControlError, match="reason"):
        validate_control_payload(
            kind="reschedule",
            control_at="2026-11-01T12:00:00+05:00",
            reason=None,
        )


def test_client_reported_response_note() -> None:
    out = validate_control_payload(
        kind="check",
        check_result="client_reported_response",
    )
    assert out["next_action_text"] == CLIENT_REPORTED_RESPONSE_NOTE
    assert out["waiting_on"] == "client"


def test_assign_requires_date_and_action() -> None:
    with pytest.raises(FollowUpControlError):
        validate_control_payload(kind="assign_control", next_action_text="x")
    out = validate_control_payload(
        kind="assign_control",
        control_at="2026-11-05T10:00:00+05:00",
        next_action_text="Уточнить у клиента, поступил ли ответ",
        expert_user_id="u1",
    )
    assert out["waiting_on"] == "sfr"
