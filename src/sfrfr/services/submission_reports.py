"""Этап 9: отчёт о подаче клиентом (форма) — валидация и сбор строки."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Literal
from uuid import uuid4

METHODS = frozenset({"gosuslugi", "sfr", "mfc", "post", "other"})
KINDS = frozenset({"client_reported", "help_requested", "receipt_verified"})
SOURCES = frozenset({"client_self", "client_words"})

PROOF_MISSING_NOTE = "Клиент сообщил о подаче; подтверждение приёма не приложено"

Decision = Literal["confirmed", "help_requested", "receipt_verified"]
ActorKind = Literal["client", "staff"]


class SubmissionReportError(ValueError):
    """Некорректные поля формы подачи."""


def audit_action_for_kind(kind: str) -> str:
    return {
        "client_reported": "submission_confirmed",
        "help_requested": "submission_help_requested",
        "receipt_verified": "submission_receipt_verified",
    }[kind]


def proof_missing_note(proof_document_id: str | None) -> str | None:
    if proof_document_id:
        return None
    return PROOF_MISSING_NOTE


def _as_uuid_or_none(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    # loose UUID shape — иначе FK insert упадёт
    parts = raw.split("-")
    if len(parts) != 5:
        raise SubmissionReportError("proof_document_id must be a document UUID")
    return raw


def _parse_date(value: str | None) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    raw = str(value).strip()[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise SubmissionReportError("submitted_on must be YYYY-MM-DD") from exc


def validate_submission_payload(
    *,
    decision: str,
    submitted_on: str | None,
    method: str | None,
    submitted_what: str | None,
    source: str | None,
    actor_kind: ActorKind,
    appeal_number: str | None = None,
    proof_document_id: str | None = None,
    comment: str | None = None,
    package_version: str | None = None,
) -> dict[str, Any]:
    d = str(decision or "").strip().lower()
    if d == "confirmed":
        kind = "client_reported"
    elif d == "help_requested":
        kind = "help_requested"
    elif d == "receipt_verified":
        kind = "receipt_verified"
    else:
        raise SubmissionReportError(
            "decision must be confirmed|help_requested|receipt_verified"
        )

    src = str(source or "").strip().lower() or (
        "client_self" if actor_kind == "client" else ""
    )
    if actor_kind == "staff" and kind == "client_reported" and src != "client_words":
        raise SubmissionReportError("staff confirm requires source=client_words")
    if actor_kind == "client":
        src = "client_self"
    if src and src not in SOURCES and kind != "receipt_verified":
        raise SubmissionReportError("source must be client_self|client_words")
    if kind == "receipt_verified":
        src = src or "client_words"

    on = _parse_date(submitted_on)
    today = datetime.now(UTC).date()
    meth = str(method or "").strip().lower() or None
    what = str(submitted_what or "").strip() or None

    if kind == "client_reported":
        if on is None:
            raise SubmissionReportError("submitted_on is required")
        if on > today:
            raise SubmissionReportError("submitted_on must not be in the future")
        if meth not in METHODS:
            raise SubmissionReportError(
                "method must be gosuslugi|sfr|mfc|post|other"
            )
        if not what:
            raise SubmissionReportError("submitted_what is required")
    elif kind == "help_requested":
        on = None
        meth = None
        what = what  # optional note
    else:
        # receipt_verified — дата/метод не обязательны (проверка приложенного)
        pass

    return {
        "kind": kind,
        "submitted_on": on.isoformat() if on else None,
        "method": meth,
        "submitted_what": what,
        "source": src or None,
        "appeal_number": (str(appeal_number).strip()[:120] if appeal_number else None)
        or None,
        "proof_document_id": _as_uuid_or_none(proof_document_id),
        "comment": (str(comment).strip()[:2000] if comment else None) or None,
        "package_version": (str(package_version).strip()[:200] if package_version else None)
        or None,
        "proof_missing": kind == "client_reported"
        and not (proof_document_id and str(proof_document_id).strip()),
    }


def build_report_row(
    *,
    case_id: str,
    actor_id: str | None,
    actor_kind: ActorKind,
    kind: str,
    submitted_on: str | None,
    method: str | None,
    submitted_what: str | None,
    source: str | None,
    idempotency_key: str,
    appeal_number: str | None = None,
    proof_document_id: str | None = None,
    comment: str | None = None,
    package_version: str | None = None,
) -> dict[str, Any]:
    if kind not in KINDS:
        raise SubmissionReportError("invalid kind")
    return {
        "id": str(uuid4()),
        "case_id": case_id,
        "actor_id": actor_id,
        "actor_kind": actor_kind,
        "kind": kind,
        "submitted_on": submitted_on,
        "method": method,
        "submitted_what": submitted_what,
        "appeal_number": appeal_number,
        "proof_document_id": proof_document_id,
        "comment": comment,
        "source": source,
        "package_version": package_version,
        "idempotency_key": idempotency_key,
    }


def serialize_report(row: dict[str, Any]) -> dict[str, Any]:
    proof_id = row.get("proof_document_id")
    kind = str(row.get("kind") or "")
    note = None
    if kind == "client_reported":
        note = proof_missing_note(str(proof_id) if proof_id else None)
    return {
        "id": str(row.get("id") or ""),
        "case_id": str(row.get("case_id") or ""),
        "created_at": row.get("created_at"),
        "actor_id": row.get("actor_id"),
        "actor_kind": row.get("actor_kind"),
        "kind": kind,
        "submitted_on": row.get("submitted_on"),
        "method": row.get("method"),
        "submitted_what": row.get("submitted_what"),
        "appeal_number": row.get("appeal_number"),
        "proof_document_id": proof_id,
        "comment": row.get("comment"),
        "source": row.get("source"),
        "package_version": row.get("package_version"),
        "proof_missing": bool(note) if kind == "client_reported" else False,
        "proof_missing_note": note,
    }
