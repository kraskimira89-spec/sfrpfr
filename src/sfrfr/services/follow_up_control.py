"""Ступень 10: контроль рассмотрения (внутренняя дата, не срок СФР)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

# Канон календаря контроля (офис): UTC+5.
CONTROL_TZ = ZoneInfo("Asia/Yekaterinburg")

CheckResult = Literal["no_response", "need_more_info", "client_reported_response"]
ControlKind = Literal["assign_control", "check", "reschedule", "response_handoff"]
UiState = Literal[
    "blocked",
    "need_assign",
    "awaiting_date",
    "due_today",
    "overdue_internal",
    "done",
]

CHECK_RESULTS = frozenset(
    {"no_response", "need_more_info", "client_reported_response"}
)
KINDS = frozenset({"assign_control", "check", "reschedule", "response_handoff"})

CLIENT_REPORTED_RESPONSE_NOTE = (
    "Клиент сообщил об ответе — запросить документ"
)


class FollowUpControlError(ValueError):
    """Некорректные поля контроля."""


def calendar_today(*, now: datetime | None = None) -> date:
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(CONTROL_TZ).date()


def control_date_of(value: str | datetime | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        try:
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            dt = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise FollowUpControlError("control_at must be ISO datetime") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CONTROL_TZ)
    return dt.astimezone(CONTROL_TZ).date()


def derive_ui_state(
    *,
    submission_confirmed: bool,
    follow_up_completed: bool,
    response_received: bool,
    has_control_at: bool,
    control_at: str | datetime | None,
    now: datetime | None = None,
) -> UiState:
    if follow_up_completed or response_received:
        return "done"
    if not submission_confirmed:
        return "blocked"
    if not has_control_at or control_at is None:
        return "need_assign"
    day = control_date_of(control_at)
    today = calendar_today(now=now)
    if day is None:
        return "need_assign"
    if day > today:
        return "awaiting_date"
    if day == today:
        return "due_today"
    return "overdue_internal"


def ui_state_label(state: UiState) -> str:
    return {
        "blocked": "Сначала зафиксируйте подачу (ступень 9)",
        "need_assign": "Нужно назначить контроль",
        "awaiting_date": "Ожидаем контрольной даты",
        "due_today": "Сегодня проверить состояние",
        "overdue_internal": "Просрочена внутренняя контрольная дата",
        "done": "Ответ передан на разбор",
    }[state]


def validate_control_payload(
    *,
    kind: str,
    control_at: str | None = None,
    next_action_text: str | None = None,
    reason: str | None = None,
    check_result: str | None = None,
    waiting_on: str | None = None,
    expert_user_id: str | None = None,
    document_id: str | None = None,
) -> dict[str, Any]:
    k = str(kind or "").strip().lower()
    if k not in KINDS:
        raise FollowUpControlError(
            "kind must be assign_control|check|reschedule|response_handoff"
        )

    text = (str(next_action_text).strip()[:500] if next_action_text else None) or None
    why = (str(reason).strip()[:500] if reason else None) or None
    result = (str(check_result).strip().lower() if check_result else None) or None
    wait = (str(waiting_on).strip().lower() if waiting_on else None) or None
    expert = (str(expert_user_id).strip() if expert_user_id else None) or None
    doc = (str(document_id).strip() if document_id else None) or None
    at = (str(control_at).strip() if control_at else None) or None

    if k == "assign_control":
        if not at:
            raise FollowUpControlError("control_at is required for assign_control")
        control_date_of(at)  # validate
        if not text:
            raise FollowUpControlError("next_action_text is required for assign_control")
        wait = wait or "sfr"
    elif k == "reschedule":
        if not at:
            raise FollowUpControlError("control_at is required for reschedule")
        control_date_of(at)
        if not why:
            raise FollowUpControlError("reason is required for reschedule")
    elif k == "check":
        if result not in CHECK_RESULTS:
            raise FollowUpControlError(
                "check_result must be no_response|need_more_info|client_reported_response"
            )
        if result == "client_reported_response" and not text:
            text = CLIENT_REPORTED_RESPONSE_NOTE
        if result == "need_more_info":
            wait = wait or "client"
        elif result == "no_response":
            wait = wait or "sfr"
        else:
            wait = wait or "client"
    elif k == "response_handoff":
        if not doc:
            raise FollowUpControlError("document_id is required for response_handoff")
        wait = wait or "staff"
        text = text or "Разбор ответа СФР (ступень 11)"

    return {
        "kind": k,
        "control_at": at,
        "next_action_text": text,
        "reason": why,
        "check_result": result,
        "waiting_on": wait,
        "expert_user_id": expert,
        "document_id": doc,
    }


def build_event_row(
    *,
    case_id: str,
    actor_id: str | None,
    kind: str,
    idempotency_key: str,
    control_at: str | None = None,
    previous_control_at: str | None = None,
    next_action_text: str | None = None,
    reason: str | None = None,
    check_result: str | None = None,
    waiting_on: str | None = None,
    expert_user_id: str | None = None,
    document_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "case_id": case_id,
        "actor_id": actor_id,
        "kind": kind,
        "check_result": check_result,
        "control_at": control_at,
        "previous_control_at": previous_control_at,
        "next_action_text": next_action_text,
        "reason": reason,
        "waiting_on": waiting_on,
        "expert_user_id": expert_user_id,
        "document_id": document_id,
        "idempotency_key": idempotency_key[:200],
    }


def serialize_event(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or ""),
        "case_id": str(row.get("case_id") or ""),
        "created_at": row.get("created_at"),
        "actor_id": row.get("actor_id"),
        "kind": row.get("kind"),
        "check_result": row.get("check_result"),
        "control_at": row.get("control_at"),
        "previous_control_at": row.get("previous_control_at"),
        "next_action_text": row.get("next_action_text"),
        "reason": row.get("reason"),
        "waiting_on": row.get("waiting_on"),
        "expert_user_id": row.get("expert_user_id"),
        "document_id": row.get("document_id"),
    }


def audit_action_for_kind(kind: str) -> str:
    return {
        "assign_control": "follow_up_control_assigned",
        "check": "follow_up_check_recorded",
        "reschedule": "follow_up_control_rescheduled",
        "response_handoff": "follow_up_response_handoff",
    }[kind]
