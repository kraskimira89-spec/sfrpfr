"""Завершение обслуживания после отказа из-за цены (§20.25 З–Н / §45–47)."""

from __future__ import annotations

from typing import Any, Final

STATUS_DISTINCTIONS: Final[tuple[tuple[str, str], ...]] = (
    ("refuse_next_purchase", "stop_current_service"),
    ("work_done", "result_delivered"),
    ("result_delivered", "result_accepted"),
    ("service_ended", "pension_resolved"),
    ("period_documented", "officially_counted"),
    ("facts_clarified", "recalculation_confirmed"),
)


def statuses_must_stay_distinct(a: str, b: str) -> bool:
    """True — эти статусы нельзя сливать (§45)."""
    return frozenset({a, b}) in {frozenset(p) for p in STATUS_DISTINCTIONS}


def delivery_vs_creation(
    *,
    file_exists: bool,
    same_case: bool,
    accessible: bool,
    announced_delivered: bool,
) -> dict[str, Any]:
    truly_delivered = file_exists and same_case and accessible
    return {
        "delivered": truly_delivered,
        "may_announce_delivered": truly_delivered and announced_delivered,
        "creation_is_not_delivery": True,
        "hold_for_next_pay": False,
    }


def silence_after_delivery_policy() -> dict[str, Any]:
    return {
        "silence_is_satisfaction": False,
        "silence_is_acceptance": False,
        "may_reoffer": False,
        "may_close_claim_on_silence": False,
        "only_prescribed_service_notices": True,
    }


def completion_pipeline_step_ok(
    *,
    refuse_saved: bool,
    obligations_checked: bool,
    unpaid_work_started: bool,
    result_accessible: bool,
    announced_success: bool,
) -> bool:
    """Не сообщать успех, если шаг не выполнен (§47)."""
    if unpaid_work_started:
        return False
    if announced_success and not (
        refuse_saved and obligations_checked and result_accessible
    ):
        return False
    return True


def final_service_summary(
    *,
    done: list[str],
    materials_access: str,
    remaining_in_order: list[str] | None,
    open_pension_questions: list[str],
    next_self_step: str | None = None,
    deadlines: list[str] | None = None,
) -> dict[str, Any]:
    """Итог §45 — без нового offer."""
    return {
        "next_paid_stage": "not_opened",
        "done": list(done),
        "materials_access": materials_access,
        "remaining_in_order": list(remaining_in_order or []),
        "open_pension_questions": list(open_pension_questions),
        "next_self_step": next_self_step,
        "deadlines": list(deadlines or []),
        "includes_new_offer": False,
        "service_end_is_not_pension_success": True,
        "refuse_next_is_not_stop_current": True,
    }
