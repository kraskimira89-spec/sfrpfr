"""Реанимация CRM-дел и orphan MAX: классификация и расписание касаний."""

from __future__ import annotations

from datetime import UTC, datetime

from sfrfr.services.case_reactivation import (
    TOUCH1_AFTER_DAYS,
    TOUCH2_AFTER_DAYS,
    basket_for_case,
    basket_for_orphan,
    message_for_touch,
    run_due_tick,
    should_send_touch,
    touch_number_due,
)


def test_basket_f_do_not_contact() -> None:
    b = basket_for_case(
        {
            "do_not_contact": True,
            "pipeline_status": "in_touch",
            "waiting_on": "client",
        },
        now=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
        silent_days=10,
        open_diag_invoice=False,
        paid_stalled=False,
    )
    assert b == "F"


def test_basket_c_open_invoice() -> None:
    b = basket_for_case(
        {
            "do_not_contact": False,
            "pipeline_status": "payment",
            "waiting_on": "payment",
            "loss_reason": None,
        },
        now=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
        silent_days=8,
        open_diag_invoice=True,
        paid_stalled=False,
    )
    assert b == "C"


def test_basket_b_waiting_client_docs() -> None:
    b = basket_for_case(
        {
            "do_not_contact": False,
            "pipeline_status": "docs",
            "waiting_on": "client",
        },
        now=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
        silent_days=6,
        open_diag_invoice=False,
        paid_stalled=False,
    )
    assert b == "B"


def test_basket_d_paid_stalled() -> None:
    b = basket_for_case(
        {
            "do_not_contact": False,
            "pipeline_status": "delivery",
            "waiting_on": "staff",
        },
        now=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
        silent_days=4,
        open_diag_invoice=False,
        paid_stalled=True,
    )
    assert b == "D"


def test_basket_a_in_touch_silence() -> None:
    b = basket_for_case(
        {
            "do_not_contact": False,
            "pipeline_status": "in_touch",
            "waiting_on": "client",
        },
        now=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
        silent_days=5,
        open_diag_invoice=False,
        paid_stalled=False,
    )
    assert b == "A"


def test_closed_or_lost_skipped() -> None:
    b = basket_for_case(
        {
            "do_not_contact": False,
            "pipeline_status": "closed",
            "waiting_on": "none",
            "loss_reason": None,
        },
        now=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
        silent_days=20,
        open_diag_invoice=False,
        paid_stalled=False,
    )
    assert b is None


def test_orphan_when_no_open_case() -> None:
    assert basket_for_orphan(max_user_id="123", open_cases=0, do_not_contact=False) == "O"
    assert basket_for_orphan(max_user_id="123", open_cases=1, do_not_contact=False) is None
    assert basket_for_orphan(max_user_id="", open_cases=0, do_not_contact=False) is None
    assert basket_for_orphan(max_user_id="123", open_cases=0, do_not_contact=True) == "F"


def test_touch_schedule() -> None:
    assert touch_number_due(touches_sent=0, silent_days=TOUCH1_AFTER_DAYS) == 1
    assert touch_number_due(touches_sent=0, silent_days=TOUCH1_AFTER_DAYS - 1) is None
    assert touch_number_due(touches_sent=1, silent_days=TOUCH1_AFTER_DAYS + TOUCH2_AFTER_DAYS) == 2
    assert touch_number_due(touches_sent=2, silent_days=40) is None


def test_messages_nonempty_and_no_recalc_promise() -> None:
    for basket in ("A", "B", "C", "O"):
        for n in (1, 2):
            text = message_for_touch(basket, n)
            assert "Здравствуйте" in text
            low = text.casefold()
            assert "перерасчёт" not in low or "не" in low
            assert "гарантир" not in low


def test_should_send_respects_policy_and_auto() -> None:
    assert (
        should_send_touch(
            auto_send=True,
            quiet_hours=False,
            contact_allowed=True,
            basket="A",
            touch_no=1,
        )
        is True
    )
    assert (
        should_send_touch(
            auto_send=False,
            quiet_hours=False,
            contact_allowed=True,
            basket="A",
            touch_no=1,
        )
        is False
    )
    assert (
        should_send_touch(
            auto_send=True,
            quiet_hours=True,
            contact_allowed=True,
            basket="A",
            touch_no=1,
        )
        is False
    )
    assert (
        should_send_touch(
            auto_send=True,
            quiet_hours=False,
            contact_allowed=True,
            basket="D",
            touch_no=1,
        )
        is False
    )
    assert (
        should_send_touch(
            auto_send=True,
            quiet_hours=False,
            contact_allowed=True,
            basket="F",
            touch_no=1,
        )
        is False
    )


def test_run_due_tick_dry_run_plans_send_and_staff() -> None:
    now = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)  # день, не quiet
    cases = [
        {
            "id": "c-a",
            "pipeline_status": "in_touch",
            "waiting_on": "client",
            "max_user_id": "1",
            "silent_days": 8,
            "reactivation_touches": 0,
            "do_not_contact": False,
        },
        {
            "id": "c-d",
            "pipeline_status": "delivery",
            "waiting_on": "staff",
            "max_user_id": "2",
            "silent_days": 5,
            "reactivation_touches": 0,
            "paid_stalled": True,
            "do_not_contact": False,
        },
    ]
    orphans = [
        {
            "client_id": "cl1",
            "max_user_id": "99",
            "open_cases": 0,
            "silent_days": 30,
            "reactivation_touches": 0,
            "do_not_contact": False,
        }
    ]
    stats = run_due_tick(
        cases=cases,
        orphans=orphans,
        now=now,
        dry_run=True,
        force_send=True,
        limit=10,
    )
    assert stats["candidates"] >= 2
    actions = {i["case_id"]: i["action"] for i in stats["items"] if i.get("case_id")}
    assert actions.get("c-a") == "send"
    assert actions.get("c-d") == "staff_task"
    assert any(i.get("kind") == "orphan" and i.get("action") == "send" for i in stats["items"])
