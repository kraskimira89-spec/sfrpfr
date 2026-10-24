"""Точечная операция исправления даты периода (SFRFR-110 / E01 prep).

Команда ≠ запись ≠ событие ≠ пересчёт ≠ сообщение клиенту.
Нет E01-wire / MAX / публичного HTTP в этом модуле.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, Protocol

from sfrfr.security.auth import Principal, StaffRole

_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_ALLOWED_FIELDS = frozenset({"date_from", "date_to"})
_ALLOWED_COLLECTIONS = frozenset({"ils_periods", "labor_periods"})


class CorrectionOutcome(StrEnum):
    """Исходы операции (имена в стиле проекта)."""

    SAVED = "saved"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    VERSION_CONFLICT = "version_conflict"
    INVALID_DATA = "invalid_data"
    NOT_FOUND_OR_FORBIDDEN = "not_found_or_forbidden"
    WRITE_REJECTED = "write_rejected"
    OP_ID_PAYLOAD_CONFLICT = "op_id_payload_conflict"
    UNKNOWN = "unknown"


class PeriodCollection(StrEnum):
    ILS = "ils_periods"
    LABOR = "labor_periods"


class PeriodDateField(StrEnum):
    DATE_FROM = "date_from"
    DATE_TO = "date_to"


@dataclass(frozen=True)
class CorrectPeriodDateCommand:
    operation_id: str
    case_id: str
    collection: PeriodCollection
    period_id: str
    field: PeriodDateField
    new_value: str
    expected_version: str
    reason: str
    value_source: str = "staff_verified"


@dataclass(frozen=True)
class PeriodDateCorrectedEvent:
    """Событие только из подтверждённой записи (не из команды)."""

    event_type: str
    operation_id: str
    case_id: str
    collection: str
    period_id: str
    field: str
    before: str | None
    after: str
    value_source: str
    correction_basis: str
    actor_id: str
    version_before: str
    version_after: str
    persisted_at: str
    persist_ack_source: str
    dependents_status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "operation_id": self.operation_id,
            "case_id": self.case_id,
            "period_ref": {
                "collection": self.collection,
                "period_id": self.period_id,
            },
            "field": self.field,
            "before": self.before,
            "after": self.after,
            "value_source": self.value_source,
            "correction_basis": self.correction_basis,
            "actor_id": self.actor_id,
            "version_before": self.version_before,
            "version_after": self.version_after,
            "persisted_at": self.persisted_at,
            "persist_ack_source": self.persist_ack_source,
            "dependent_results": ["findings", "draft", "client_facing_claims"],
            "dependents_status": self.dependents_status,
        }


@dataclass(frozen=True)
class CorrectPeriodDateResult:
    outcome: CorrectionOutcome
    event: PeriodDateCorrectedEvent | None = None
    detail: str | None = None
    version_after: str | None = None
    dependents_status: str | None = None

    @property
    def confirmed(self) -> bool:
        return self.outcome in {
            CorrectionOutcome.SAVED,
            CorrectionOutcome.IDEMPOTENT_REPLAY,
        }


@dataclass
class StoreApplySuccess:
    event: PeriodDateCorrectedEvent
    version_after: str


@dataclass
class StoreApplyFailure:
    outcome: CorrectionOutcome
    detail: str | None = None
    event: PeriodDateCorrectedEvent | None = None


class PeriodDateCorrectionStore(Protocol):
    """Хранилище с атомарной границей version + запись + событие."""

    def apply_correction(
        self,
        *,
        command: CorrectPeriodDateCommand,
        actor_id: str,
    ) -> StoreApplySuccess | StoreApplyFailure: ...

    def lookup_by_operation_id(
        self,
        *,
        case_id: str,
        operation_id: str,
    ) -> PeriodDateCorrectedEvent | None: ...


def parse_iso_date(value: str) -> date | None:
    raw = (value or "").strip()
    m = _DATE_RE.match(raw)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def validate_command_shape(command: CorrectPeriodDateCommand) -> str | None:
    if not str(command.operation_id or "").strip():
        return "operation_id required"
    if not str(command.case_id or "").strip():
        return "case_id required"
    if not str(command.period_id or "").strip():
        return "period_id required"
    if command.collection.value not in _ALLOWED_COLLECTIONS:
        return "unknown collection"
    if command.field.value not in _ALLOWED_FIELDS:
        return "unknown field"
    if not str(command.reason or "").strip():
        return "reason required"
    if not str(command.expected_version or "").strip():
        return "expected_version required"
    if parse_iso_date(command.new_value) is None:
        return "invalid date"
    if command.value_source not in {
        "ocr_extract",
        "client_said",
        "staff_verified",
        "system_derived",
    }:
        return "invalid value_source"
    return None


def validate_period_interval(period: dict[str, Any], field: str, new_value: str) -> str | None:
    """Проверка интервала после подстановки нового значения."""
    date_from = period.get("date_from")
    date_to = period.get("date_to")
    if field == "date_from":
        date_from = new_value
    elif field == "date_to":
        date_to = new_value
    df = parse_iso_date(str(date_from)) if date_from else None
    dt = parse_iso_date(str(date_to)) if date_to else None
    if date_from and df is None:
        return "invalid date_from"
    if date_to and dt is None:
        return "invalid date_to"
    if df is not None and dt is not None and df > dt:
        return "date_from after date_to"
    return None


def actor_may_correct(*, principal: Principal) -> bool:
    """Только staff/job-контур: клиент и MAX-only не пишут дату."""
    if principal.is_max_only:
        return False
    if not principal.is_staff:
        return False
    return principal.role in {
        StaffRole.ADMIN,
        StaffRole.OPERATOR,
        StaffRole.EXPERT,
    }


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def build_event(
    *,
    command: CorrectPeriodDateCommand,
    actor_id: str,
    before: str | None,
    version_before: str,
    version_after: str,
    persisted_at: str,
    persist_ack_source: str = "db_write_ack",
) -> PeriodDateCorrectedEvent:
    return PeriodDateCorrectedEvent(
        event_type="period_date_corrected",
        operation_id=command.operation_id,
        case_id=command.case_id,
        collection=command.collection.value,
        period_id=command.period_id,
        field=command.field.value,
        before=before,
        after=command.new_value,
        value_source=command.value_source,
        correction_basis=command.reason,
        actor_id=actor_id,
        version_before=version_before,
        version_after=version_after,
        persisted_at=persisted_at,
        persist_ack_source=persist_ack_source,
        dependents_status="needs_recheck",
    )


def command_fingerprint(command: CorrectPeriodDateCommand) -> dict[str, str]:
    return {
        "collection": command.collection.value,
        "period_id": command.period_id,
        "field": command.field.value,
        "new_value": command.new_value,
        "reason": command.reason,
        "value_source": command.value_source,
    }


def event_matches_command(
    event: PeriodDateCorrectedEvent, command: CorrectPeriodDateCommand
) -> bool:
    fp = command_fingerprint(command)
    return (
        event.collection == fp["collection"]
        and event.period_id == fp["period_id"]
        and event.field == fp["field"]
        and event.after == fp["new_value"]
        and event.correction_basis == fp["reason"]
        and event.value_source == fp["value_source"]
    )


def correct_period_date(
    command: CorrectPeriodDateCommand,
    *,
    principal: Principal,
    store: PeriodDateCorrectionStore,
    case_accessible: bool,
) -> CorrectPeriodDateResult:
    """Выполнить операцию. case_accessible — результат require_case/can_access снаружи."""
    if not actor_may_correct(principal=principal):
        return CorrectPeriodDateResult(
            outcome=CorrectionOutcome.NOT_FOUND_OR_FORBIDDEN,
            detail="forbidden",
        )
    if not case_accessible:
        return CorrectPeriodDateResult(
            outcome=CorrectionOutcome.NOT_FOUND_OR_FORBIDDEN,
            detail="case not found",
        )

    shape_err = validate_command_shape(command)
    if shape_err:
        return CorrectPeriodDateResult(
            outcome=CorrectionOutcome.INVALID_DATA,
            detail=shape_err,
        )

    actor_id = principal.audit_actor_id() or principal.user_id
    try:
        applied = store.apply_correction(command=command, actor_id=actor_id)
    except Exception as exc:  # noqa: BLE001 — неизвестный исход → сверка, не success
        return CorrectPeriodDateResult(
            outcome=CorrectionOutcome.UNKNOWN,
            detail=f"apply_error:{type(exc).__name__}",
        )

    if isinstance(applied, StoreApplySuccess):
        return CorrectPeriodDateResult(
            outcome=CorrectionOutcome.SAVED,
            event=applied.event,
            version_after=applied.version_after,
            dependents_status=applied.event.dependents_status,
        )

    if applied.outcome == CorrectionOutcome.IDEMPOTENT_REPLAY and applied.event is not None:
        return CorrectPeriodDateResult(
            outcome=CorrectionOutcome.IDEMPOTENT_REPLAY,
            event=applied.event,
            version_after=applied.event.version_after,
            dependents_status=applied.event.dependents_status,
            detail=applied.detail,
        )

    return CorrectPeriodDateResult(
        outcome=applied.outcome,
        event=applied.event,
        detail=applied.detail,
        version_after=applied.event.version_after if applied.event else None,
        dependents_status=(
            applied.event.dependents_status if applied.event else None
        ),
    )


def reconcile_unknown(
    *,
    case_id: str,
    operation_id: str,
    store: PeriodDateCorrectionStore,
) -> CorrectPeriodDateResult:
    """Сверка после UNKNOWN: не слепое повторное изменение."""
    event = store.lookup_by_operation_id(case_id=case_id, operation_id=operation_id)
    if event is None:
        return CorrectPeriodDateResult(
            outcome=CorrectionOutcome.UNKNOWN,
            detail="not_found_after_unknown",
        )
    return CorrectPeriodDateResult(
        outcome=CorrectionOutcome.IDEMPOTENT_REPLAY,
        event=event,
        version_after=event.version_after,
        dependents_status=event.dependents_status,
        detail="reconciled",
    )


def mark_dependents_needs_recheck(findings: list[Any] | None) -> list[dict[str, Any]]:
    """Явная актуальность: needs_recheck, без статуса «пересчитано»."""
    out: list[dict[str, Any]] = []
    for item in findings or []:
        if isinstance(item, dict):
            row = dict(item)
        else:
            row = {"raw": item}
        row.pop("recalculated", None)
        row.pop("pension_recalculated", None)
        row["depends_on_period_date"] = True
        row["dependents_status"] = "needs_recheck"
        if row.get("status") in {"recalculated", "pension_updated"}:
            row["status"] = "needs_recheck"
        out.append(row)
    return out


def merge_periods_preserve_corrections(
    *,
    existing: list[Any] | None,
    incoming: list[Any] | None,
) -> list[dict[str, Any]]:
    """Pipeline snapshot не затирает staff-исправления по period_id."""
    existing_rows = [dict(x) for x in (existing or []) if isinstance(x, dict)]
    incoming_rows = [dict(x) for x in (incoming or []) if isinstance(x, dict)]
    by_id = {
        str(p.get("period_id")): p
        for p in existing_rows
        if str(p.get("period_id") or "").strip()
        and p.get("staff_date_correction")
    }
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in incoming_rows:
        pid = str(row.get("period_id") or "").strip()
        if pid and pid in by_id:
            preserved = dict(by_id[pid])
            # OCR/pipeline может обновить employer и пр., но даты — из correction.
            for key in ("employer", "source"):
                if key in row and row[key] is not None:
                    preserved[key] = row[key]
            merged.append(preserved)
            seen.add(pid)
        else:
            merged.append(row)
            if pid:
                seen.add(pid)
    for pid, preserved in by_id.items():
        if pid not in seen:
            merged.append(preserved)
    return merged
