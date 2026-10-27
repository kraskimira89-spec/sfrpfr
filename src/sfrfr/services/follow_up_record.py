"""Запись события контроля + обновление cases.next_action*."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sfrfr.db.case_repository import CaseRepository
from sfrfr.services.follow_up_control import (
    FollowUpControlError,
    audit_action_for_kind,
    build_event_row,
    serialize_event,
    validate_control_payload,
)


def record_follow_up_control(
    repo: CaseRepository,
    *,
    case_id: str,
    actor_id: str | None,
    payload: dict[str, Any],
    case_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = dict(payload or {})
    kind = str(body.get("kind") or "").strip().lower()
    idem = str(body.get("idempotency_key") or "").strip() or None
    if not idem:
        parts = [
            case_id,
            kind,
            str(body.get("control_at") or ""),
            str(body.get("check_result") or ""),
            str(body.get("reason") or ""),
            str(uuid4()),
        ]
        idem = ":".join(parts)[:200]

    existing = repo.get_follow_up_event_by_idempotency(idem)
    if existing:
        return {
            "ok": True,
            "replayed": True,
            "action": audit_action_for_kind(str(existing.get("kind") or kind)),
            "event": serialize_event(existing),
            "case": case_row,
        }

    validated = validate_control_payload(
        kind=kind,
        control_at=body.get("control_at"),
        next_action_text=body.get("next_action_text"),
        reason=body.get("reason"),
        check_result=body.get("check_result"),
        waiting_on=body.get("waiting_on"),
        expert_user_id=body.get("expert_user_id"),
        document_id=body.get("document_id"),
    )

    previous = (case_row or {}).get("next_action_at") if case_row else None

    row = build_event_row(
        case_id=case_id,
        actor_id=actor_id,
        kind=str(validated["kind"]),
        idempotency_key=idem,
        control_at=validated.get("control_at"),
        previous_control_at=str(previous) if previous else None,
        next_action_text=validated.get("next_action_text"),
        reason=validated.get("reason"),
        check_result=validated.get("check_result"),
        waiting_on=validated.get("waiting_on"),
        expert_user_id=validated.get("expert_user_id"),
        document_id=validated.get("document_id"),
    )
    inserted = repo.insert_follow_up_event(row)
    is_new = str(inserted.get("id")) == str(row["id"])

    updated_case = case_row
    if is_new:
        k = str(validated["kind"])
        if k in {"assign_control", "reschedule"}:
            updated_case = repo.update_next_action(
                case_id,
                actor_id,
                next_action=validated.get("next_action_text"),
                next_action_at=validated.get("control_at"),
                waiting_on=validated.get("waiting_on") or "sfr",
            )
            expert = validated.get("expert_user_id")
            if expert:
                updated_case = repo.assign_expert(case_id, expert, actor_id or "")
        elif k == "check":
            # Дату контроля не сбрасываем — только действие и waiting_on.
            updated_case = repo.update_next_action(
                case_id,
                actor_id,
                next_action=validated.get("next_action_text")
                or (case_row or {}).get("next_action"),
                waiting_on=validated.get("waiting_on") or "sfr",
            )
        elif k == "response_handoff":
            updated_case = repo.update_next_action(
                case_id,
                actor_id,
                next_action=validated.get("next_action_text"),
                next_action_at="",  # clear internal control date
                waiting_on="staff",
            )
            repo.audit(case_id, actor_id, "follow_up_completed")
            # Сразу открыть строку на ступени 11 (idempotent).
            doc_id = str(validated.get("document_id") or "").strip()
            if doc_id:
                try:
                    from sfrfr.services.response_review_record import (
                        register_response_review,
                    )

                    register_response_review(
                        repo,
                        case_id=case_id,
                        actor_id=actor_id,
                        payload={
                            "document_id": doc_id,
                            "source": "staff",
                            "completeness": "unknown",
                            "respondent": "sfr",
                            "response_kind": "decision",
                            "idempotency_key": f"handoff:{doc_id}"[:200],
                        },
                    )
                except Exception:  # noqa: BLE001
                    pass
        repo.audit(case_id, actor_id, audit_action_for_kind(k))

    return {
        "ok": True,
        "replayed": not is_new,
        "action": audit_action_for_kind(str(inserted.get("kind") or kind)),
        "event": serialize_event(inserted),
        "case": updated_case,
    }


# re-export for callers that catch validation
__all__ = ["FollowUpControlError", "record_follow_up_control"]
