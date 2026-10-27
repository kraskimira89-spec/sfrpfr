"""Запись отчёта о подаче + audit (admin/client API)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sfrfr.db.case_repository import CaseRepository
from sfrfr.services.submission_reports import (
    ActorKind,
    audit_action_for_kind,
    build_report_row,
    serialize_report,
    validate_submission_payload,
)


def record_case_submission(
    repo: CaseRepository,
    *,
    case_id: str,
    actor_id: str | None,
    actor_kind: ActorKind,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Validate → insert report (idempotent) → audit if new → serialized response."""
    decision = str(payload.get("decision") or "").strip().lower()
    idem = str(payload.get("idempotency_key") or "").strip() or None
    if not idem:
        # Stable-ish key for double-click without client key: case+decision+date+actor+day
        submitted_on = str(payload.get("submitted_on") or "").strip()[:10]
        idem = (
            f"{case_id}:{decision}:{submitted_on}:{actor_kind}:{actor_id or 'anon'}"
            f":{payload.get('method') or ''}:{payload.get('submitted_what') or ''}"
        )[:200]
        if decision == "help_requested":
            idem = f"{case_id}:help:{actor_kind}:{actor_id or 'anon'}"[:200]
        if decision == "receipt_verified":
            idem = f"{case_id}:receipt_verified:{actor_id or 'anon'}:{uuid4()}"[:200]

    existing = repo.get_submission_report_by_idempotency(idem)
    if existing:
        return {
            "ok": True,
            "replayed": True,
            "decision": decision,
            "action": audit_action_for_kind(str(existing.get("kind") or "client_reported")),
            "report": serialize_report(existing),
        }

    validated = validate_submission_payload(
        decision=decision,
        submitted_on=payload.get("submitted_on"),
        method=payload.get("method"),
        submitted_what=payload.get("submitted_what"),
        source=payload.get("source"),
        actor_kind=actor_kind,
        appeal_number=payload.get("appeal_number"),
        proof_document_id=payload.get("proof_document_id"),
        comment=payload.get("comment"),
        package_version=payload.get("package_version"),
    )

    row = build_report_row(
        case_id=case_id,
        actor_id=actor_id,
        actor_kind=actor_kind,
        kind=str(validated["kind"]),
        submitted_on=validated.get("submitted_on"),
        method=validated.get("method"),
        submitted_what=validated.get("submitted_what"),
        source=validated.get("source"),
        idempotency_key=idem,
        appeal_number=validated.get("appeal_number"),
        proof_document_id=validated.get("proof_document_id"),
        comment=validated.get("comment"),
        package_version=validated.get("package_version"),
    )
    inserted = repo.insert_submission_report(row)
    # If race lost, insert returns existing — only audit when id matches new row
    is_new = str(inserted.get("id")) == str(row["id"])
    action = audit_action_for_kind(str(inserted.get("kind") or validated["kind"]))
    if is_new:
        repo.audit(case_id, actor_id, action)
    return {
        "ok": True,
        "replayed": not is_new,
        "decision": decision,
        "action": action,
        "report": serialize_report(inserted),
    }
