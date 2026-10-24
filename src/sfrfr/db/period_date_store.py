"""Хранилище точечной правки даты периода.

Атомарность: одна граница «прочитать FOR UPDATE / сверить version /
записать periods+findings+embedded event». Отдельный access_audit после
успеха не используется как доказательство (запрет двойного write).
"""

from __future__ import annotations

import threading
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from sfrfr.core.config import get_settings
from sfrfr.services.period_date_correction import (
    CorrectionOutcome,
    CorrectPeriodDateCommand,
    PeriodDateCorrectedEvent,
    StoreApplyFailure,
    StoreApplySuccess,
    build_event,
    event_matches_command,
    mark_dependents_needs_recheck,
    utc_now_iso,
    validate_period_interval,
)


def _psycopg_dsn(url: str) -> str:
    raw = (url or "").strip()
    if raw.startswith("postgresql+psycopg://"):
        return "postgresql://" + raw[len("postgresql+psycopg://") :]
    return raw


@dataclass
class _CasePipelineState:
    ils_periods: list[dict[str, Any]] = field(default_factory=list)
    labor_periods: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    draft: dict[str, Any] | None = None
    version: str = "1"
    operations: dict[str, PeriodDateCorrectedEvent] = field(default_factory=dict)


class InMemoryPeriodDateStore:
    """Потокобезопасный CAS-store для unit-тестов (не замена БД)."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cases: dict[str, _CasePipelineState] = {}
        self.fail_next_write: bool = False
        self.raise_on_apply: BaseException | None = None

    def seed(
        self,
        case_id: str,
        *,
        ils_periods: list[dict[str, Any]] | None = None,
        labor_periods: list[dict[str, Any]] | None = None,
        findings: list[dict[str, Any]] | None = None,
        draft: dict[str, Any] | None = None,
        version: str = "1",
    ) -> None:
        with self._lock:
            self._cases[case_id] = _CasePipelineState(
                ils_periods=deepcopy(ils_periods or []),
                labor_periods=deepcopy(labor_periods or []),
                findings=deepcopy(findings or []),
                draft=deepcopy(draft) if draft else None,
                version=str(version),
            )

    def get_state(self, case_id: str) -> _CasePipelineState | None:
        with self._lock:
            st = self._cases.get(case_id)
            return deepcopy(st) if st else None

    def apply_pipeline_snapshot(
        self,
        case_id: str,
        snapshot: dict[str, Any] | None = None,
        *,
        expected_version: str | None = None,
        ils_periods: list[dict[str, Any]] | None = None,
        labor_periods: list[dict[str, Any]] | None = None,
        findings: list[dict[str, Any]] | None = None,
    ) -> SnapshotSaveResult:
        """CAS snapshot под тем же lock, что и date-op (сценарии A–E)."""
        payload = dict(snapshot or {})
        if ils_periods is not None:
            payload["ils_periods"] = ils_periods
        if labor_periods is not None:
            payload["labor_periods"] = labor_periods
        if findings is not None:
            payload["findings"] = findings
        with self._lock:
            st = self._cases.setdefault(case_id, _CasePipelineState())
            if expected_version is not None and st.version != expected_version:
                return SnapshotSaveResult(
                    ok=False,
                    outcome="version_conflict",
                    detail="snapshot version mismatch",
                )
            ils_out, labor_out, findings_out, draft_out = _merge_snapshot_payload(
                existing_ils=st.ils_periods,
                existing_labor=st.labor_periods,
                existing_findings=st.findings,
                snapshot=payload,
            )
            st.ils_periods = ils_out
            st.labor_periods = labor_out
            st.findings = findings_out
            if draft_out is not _MISSING:
                st.draft = deepcopy(draft_out) if isinstance(draft_out, dict) else draft_out
            st.version = str(int(st.version) + 1)
            return SnapshotSaveResult(
                ok=True, outcome="saved", version_after=st.version
            )

    def lookup_by_operation_id(
        self, *, case_id: str, operation_id: str
    ) -> PeriodDateCorrectedEvent | None:
        with self._lock:
            st = self._cases.get(case_id)
            if not st:
                return None
            return st.operations.get(operation_id)

    def apply_correction(
        self,
        *,
        command: CorrectPeriodDateCommand,
        actor_id: str,
    ) -> StoreApplySuccess | StoreApplyFailure:
        if self.raise_on_apply is not None:
            exc = self.raise_on_apply
            self.raise_on_apply = None
            raise exc
        with self._lock:
            return self._apply_locked(command=command, actor_id=actor_id)

    def _apply_locked(
        self,
        *,
        command: CorrectPeriodDateCommand,
        actor_id: str,
    ) -> StoreApplySuccess | StoreApplyFailure:
        st = self._cases.get(command.case_id)
        if st is None:
            return StoreApplyFailure(
                outcome=CorrectionOutcome.NOT_FOUND_OR_FORBIDDEN,
                detail="pipeline missing",
            )

        existing = st.operations.get(command.operation_id)
        if existing is not None:
            if event_matches_command(existing, command):
                return StoreApplyFailure(
                    outcome=CorrectionOutcome.IDEMPOTENT_REPLAY,
                    event=existing,
                    detail="replay",
                )
            return StoreApplyFailure(
                outcome=CorrectionOutcome.OP_ID_PAYLOAD_CONFLICT,
                detail="operation_id payload mismatch",
                event=existing,
            )

        if st.version != command.expected_version:
            return StoreApplyFailure(
                outcome=CorrectionOutcome.VERSION_CONFLICT,
                detail="version mismatch",
            )

        collection = (
            st.ils_periods
            if command.collection.value == "ils_periods"
            else st.labor_periods
        )
        idx = next(
            (
                i
                for i, p in enumerate(collection)
                if str(p.get("period_id") or "") == command.period_id
            ),
            None,
        )
        if idx is None:
            return StoreApplyFailure(
                outcome=CorrectionOutcome.NOT_FOUND_OR_FORBIDDEN,
                detail="period not found",
            )

        period = dict(collection[idx])
        field = command.field.value
        if field not in period and field not in {"date_from", "date_to"}:
            return StoreApplyFailure(
                outcome=CorrectionOutcome.INVALID_DATA,
                detail="field not allowed",
            )
        interval_err = validate_period_interval(period, field, command.new_value)
        if interval_err:
            return StoreApplyFailure(
                outcome=CorrectionOutcome.INVALID_DATA,
                detail=interval_err,
            )

        before = period.get(field)
        before_s = str(before) if before is not None else None
        period[field] = command.new_value
        version_after = str(int(st.version) + 1)
        persisted_at = utc_now_iso()
        event = build_event(
            command=command,
            actor_id=actor_id,
            before=before_s,
            version_before=st.version,
            version_after=version_after,
            persisted_at=persisted_at,
            persist_ack_source="repository_update_ok",
        )
        _embed_correction_on_period(period, event)
        period["value_source"] = command.value_source

        if self.fail_next_write:
            self.fail_next_write = False
            return StoreApplyFailure(
                outcome=CorrectionOutcome.WRITE_REJECTED,
                detail="forced write failure",
            )

        new_collection = list(collection)
        new_collection[idx] = period
        if command.collection.value == "ils_periods":
            st.ils_periods = new_collection
        else:
            st.labor_periods = new_collection
        st.findings = mark_dependents_needs_recheck(st.findings)
        if isinstance(st.draft, dict):
            draft = dict(st.draft)
            draft.pop("recalculated", None)
            draft["dependents_status"] = "needs_recheck"
            st.draft = draft
        st.version = version_after
        st.operations[command.operation_id] = event
        return StoreApplySuccess(event=event, version_after=version_after)


class PostgresPeriodDateStore:
    """CAS через SELECT FOR UPDATE + UPDATE в одной транзакции psycopg."""

    def __init__(self, dsn: str | None = None) -> None:
        settings = get_settings()
        self._dsn = _psycopg_dsn(dsn or settings.database_url)
        # Только для integration: исключение до UPDATE → rollback всей TX.
        self.raise_before_update: BaseException | None = None

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn, row_factory=dict_row)

    def lookup_by_operation_id(
        self, *, case_id: str, operation_id: str
    ) -> PeriodDateCorrectedEvent | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select ils_periods, labor_periods
                    from public.case_pipeline_data
                    where case_id = %s::uuid
                    """,
                    (case_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return _find_event_in_periods(
            list(row.get("ils_periods") or []) + list(row.get("labor_periods") or []),
            operation_id,
        )

    def apply_correction(
        self,
        *,
        command: CorrectPeriodDateCommand,
        actor_id: str,
    ) -> StoreApplySuccess | StoreApplyFailure:
        try:
            with self._connect() as conn:
                with conn.transaction():
                    with conn.cursor() as cur:
                        return self._apply_in_tx(
                            cur, command=command, actor_id=actor_id
                        )
        except Exception as exc:  # noqa: BLE001
            # После возможного commit-сбоя вызывающий делает reconcile.
            return StoreApplyFailure(
                outcome=CorrectionOutcome.UNKNOWN,
                detail=f"tx_error:{type(exc).__name__}:{exc}",
            )

    def _apply_in_tx(
        self,
        cur: Any,
        *,
        command: CorrectPeriodDateCommand,
        actor_id: str,
    ) -> StoreApplySuccess | StoreApplyFailure:
        cur.execute(
            """
            select ils_periods, labor_periods, findings, draft, updated_at
            from public.case_pipeline_data
            where case_id = %s::uuid
            for update
            """,
            (command.case_id,),
        )
        row = cur.fetchone()
        if not row:
            return StoreApplyFailure(
                outcome=CorrectionOutcome.NOT_FOUND_OR_FORBIDDEN,
                detail="pipeline missing",
            )

        version_token = _version_token(row["updated_at"])
        ils = [dict(x) for x in (row.get("ils_periods") or []) if isinstance(x, dict)]
        labor = [dict(x) for x in (row.get("labor_periods") or []) if isinstance(x, dict)]
        findings = list(row.get("findings") or [])
        draft = row.get("draft")

        existing = _find_event_in_periods(ils + labor, command.operation_id)
        if existing is not None:
            if event_matches_command(existing, command):
                return StoreApplyFailure(
                    outcome=CorrectionOutcome.IDEMPOTENT_REPLAY,
                    event=existing,
                    detail="replay",
                )
            return StoreApplyFailure(
                outcome=CorrectionOutcome.OP_ID_PAYLOAD_CONFLICT,
                detail="operation_id payload mismatch",
                event=existing,
            )

        if version_token != command.expected_version:
            return StoreApplyFailure(
                outcome=CorrectionOutcome.VERSION_CONFLICT,
                detail="version mismatch",
            )

        collection = ils if command.collection.value == "ils_periods" else labor
        idx = next(
            (
                i
                for i, p in enumerate(collection)
                if str(p.get("period_id") or "") == command.period_id
            ),
            None,
        )
        if idx is None:
            return StoreApplyFailure(
                outcome=CorrectionOutcome.NOT_FOUND_OR_FORBIDDEN,
                detail="period not found",
            )

        period = dict(collection[idx])
        field = command.field.value
        interval_err = validate_period_interval(period, field, command.new_value)
        if interval_err:
            return StoreApplyFailure(
                outcome=CorrectionOutcome.INVALID_DATA,
                detail=interval_err,
            )

        before = period.get(field)
        before_s = str(before) if before is not None else None
        period[field] = command.new_value
        persisted_at = utc_now_iso()
        new_updated_at = datetime.now(UTC).replace(microsecond=0)
        version_after = _version_token(new_updated_at)
        event = build_event(
            command=command,
            actor_id=actor_id,
            before=before_s,
            version_before=version_token,
            version_after=version_after,
            persisted_at=persisted_at,
            persist_ack_source="db_write_ack",
        )
        _embed_correction_on_period(period, event)
        period["value_source"] = command.value_source
        collection[idx] = period
        new_findings = mark_dependents_needs_recheck(findings)
        new_draft = draft
        if isinstance(draft, dict):
            new_draft = dict(draft)
            new_draft.pop("recalculated", None)
            new_draft["dependents_status"] = "needs_recheck"

        ils_out = collection if command.collection.value == "ils_periods" else ils
        labor_out = collection if command.collection.value == "labor_periods" else labor

        if self.raise_before_update is not None:
            exc = self.raise_before_update
            self.raise_before_update = None
            raise exc

        cur.execute(
            """
            update public.case_pipeline_data
            set ils_periods = %s::jsonb,
                labor_periods = %s::jsonb,
                findings = %s::jsonb,
                draft = %s::jsonb,
                updated_at = %s
            where case_id = %s::uuid
              and updated_at = %s
            returning updated_at
            """,
            (
                Json(ils_out),
                Json(labor_out),
                Json(new_findings),
                Json(new_draft) if new_draft is not None else None,
                new_updated_at,
                command.case_id,
                row["updated_at"],
            ),
        )
        updated = cur.fetchone()
        if not updated:
            return StoreApplyFailure(
                outcome=CorrectionOutcome.VERSION_CONFLICT,
                detail="concurrent update",
            )
        return StoreApplySuccess(event=event, version_after=version_after)

    def save_pipeline_snapshot(
        self,
        case_id: str,
        snapshot: dict[str, Any],
        *,
        expected_version: str | None = None,
    ) -> SnapshotSaveResult:
        """Одна TX: FOR UPDATE → merge corrections → CAS по updated_at."""
        try:
            with self._connect() as conn:
                with conn.transaction():
                    with conn.cursor() as cur:
                        return self._save_snapshot_in_tx(
                            cur,
                            case_id=case_id,
                            snapshot=snapshot,
                            expected_version=expected_version,
                        )
        except Exception as exc:  # noqa: BLE001
            return SnapshotSaveResult(
                ok=False,
                outcome="unknown",
                detail=f"tx_error:{type(exc).__name__}:{exc}",
            )

    def _save_snapshot_in_tx(
        self,
        cur: Any,
        *,
        case_id: str,
        snapshot: dict[str, Any],
        expected_version: str | None,
    ) -> SnapshotSaveResult:
        cur.execute(
            """
            select ils_periods, labor_periods, findings, draft, updated_at,
                   ocr_texts, classifications, analysis_notes, error
            from public.case_pipeline_data
            where case_id = %s::uuid
            for update
            """,
            (case_id,),
        )
        row = cur.fetchone()
        if not row:
            # insert new row only when no pipeline yet — без затирания чужих данных
            ils_out, labor_out, findings_out, draft_out = _merge_snapshot_payload(
                existing_ils=[],
                existing_labor=[],
                existing_findings=[],
                snapshot=snapshot,
            )
            new_updated_at = datetime.now(UTC).replace(microsecond=0)
            cur.execute(
                """
                insert into public.case_pipeline_data
                  (case_id, ils_periods, labor_periods, findings, draft,
                   ocr_texts, classifications, analysis_notes, error, updated_at)
                values
                  (%s::uuid, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                   %s::jsonb, %s::jsonb, %s, %s, %s)
                """,
                (
                    case_id,
                    Json(ils_out),
                    Json(labor_out),
                    Json(findings_out),
                    Json(draft_out) if draft_out is not _MISSING else None,
                    Json(snapshot.get("ocr_texts") or []),
                    Json(snapshot.get("classifications") or []),
                    snapshot.get("analysis_notes"),
                    snapshot.get("error"),
                    new_updated_at,
                ),
            )
            return SnapshotSaveResult(
                ok=True,
                outcome="saved",
                version_after=_version_token(new_updated_at),
            )

        version_token = _version_token(row["updated_at"])
        if expected_version is not None and version_token != expected_version:
            return SnapshotSaveResult(
                ok=False,
                outcome="version_conflict",
                detail="snapshot version mismatch",
            )

        ils_out, labor_out, findings_out, draft_out = _merge_snapshot_payload(
            existing_ils=list(row.get("ils_periods") or []),
            existing_labor=list(row.get("labor_periods") or []),
            existing_findings=list(row.get("findings") or []),
            snapshot=snapshot,
        )
        new_updated_at = datetime.now(UTC).replace(microsecond=0)
        draft_sql = row.get("draft") if draft_out is _MISSING else draft_out
        ocr = (
            snapshot["ocr_texts"]
            if "ocr_texts" in snapshot
            else (row.get("ocr_texts") or [])
        )
        classifications = (
            snapshot["classifications"]
            if "classifications" in snapshot
            else (row.get("classifications") or [])
        )
        analysis_notes = (
            snapshot["analysis_notes"]
            if "analysis_notes" in snapshot
            else row.get("analysis_notes")
        )
        error = snapshot["error"] if "error" in snapshot else row.get("error")

        cur.execute(
            """
            update public.case_pipeline_data
            set ils_periods = %s::jsonb,
                labor_periods = %s::jsonb,
                findings = %s::jsonb,
                draft = %s::jsonb,
                ocr_texts = %s::jsonb,
                classifications = %s::jsonb,
                analysis_notes = %s,
                error = %s,
                updated_at = %s
            where case_id = %s::uuid
              and updated_at = %s
            returning updated_at
            """,
            (
                Json(ils_out),
                Json(labor_out),
                Json(findings_out),
                Json(draft_sql) if draft_sql is not None else None,
                Json(ocr if isinstance(ocr, list) else []),
                Json(classifications if isinstance(classifications, list) else []),
                analysis_notes,
                error,
                new_updated_at,
                case_id,
                row["updated_at"],
            ),
        )
        updated = cur.fetchone()
        if not updated:
            return SnapshotSaveResult(
                ok=False,
                outcome="version_conflict",
                detail="concurrent snapshot",
            )
        return SnapshotSaveResult(
            ok=True,
            outcome="saved",
            version_after=_version_token(new_updated_at),
        )


def _version_token(updated_at: Any) -> str:
    if isinstance(updated_at, datetime):
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        return updated_at.isoformat()
    return str(updated_at)


def _embed_correction_on_period(
    period: dict[str, Any], event: PeriodDateCorrectedEvent
) -> None:
    """Последняя правка + append-only история (старый op_id остаётся находимым)."""
    payload = event.as_dict()
    history = period.get("staff_date_corrections")
    if not isinstance(history, list):
        history = []
        legacy = period.get("staff_date_correction")
        if isinstance(legacy, dict) and legacy.get("operation_id"):
            history.append(legacy)
    history = [x for x in history if isinstance(x, dict)]
    # не дублировать тот же operation_id
    if not any(str(x.get("operation_id") or "") == event.operation_id for x in history):
        history.append(payload)
    period["staff_date_corrections"] = history
    period["staff_date_correction"] = payload


def _iter_correction_dicts(period: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    hist = period.get("staff_date_corrections")
    if isinstance(hist, list):
        out.extend(x for x in hist if isinstance(x, dict))
    latest = period.get("staff_date_correction")
    if isinstance(latest, dict):
        oid = str(latest.get("operation_id") or "")
        if oid and not any(str(x.get("operation_id") or "") == oid for x in out):
            out.append(latest)
    return out


def _find_event_in_periods(
    periods: list[Any], operation_id: str
) -> PeriodDateCorrectedEvent | None:
    for item in periods:
        if not isinstance(item, dict):
            continue
        for raw in _iter_correction_dicts(item):
            if str(raw.get("operation_id") or "") != operation_id:
                continue
            return _event_from_dict(raw)
    return None


def _event_from_dict(raw: dict[str, Any]) -> PeriodDateCorrectedEvent:
    pref = raw.get("period_ref") if isinstance(raw.get("period_ref"), dict) else {}
    return PeriodDateCorrectedEvent(
        event_type=str(raw.get("event_type") or "period_date_corrected"),
        operation_id=str(raw.get("operation_id") or ""),
        case_id=str(raw.get("case_id") or ""),
        collection=str(pref.get("collection") or ""),
        period_id=str(pref.get("period_id") or ""),
        field=str(raw.get("field") or ""),
        before=None if raw.get("before") is None else str(raw.get("before")),
        after=str(raw.get("after") or ""),
        value_source=str(raw.get("value_source") or ""),
        correction_basis=str(raw.get("correction_basis") or ""),
        actor_id=str(raw.get("actor_id") or ""),
        version_before=str(raw.get("version_before") or ""),
        version_after=str(raw.get("version_after") or ""),
        persisted_at=str(raw.get("persisted_at") or ""),
        persist_ack_source=str(raw.get("persist_ack_source") or ""),
        dependents_status=str(raw.get("dependents_status") or "needs_recheck"),
    )


@dataclass(frozen=True)
class SnapshotSaveResult:
    """Результат CAS-сохранения pipeline snapshot."""

    ok: bool
    outcome: str
    version_after: str | None = None
    detail: str | None = None


_MISSING = object()


def _merge_snapshot_payload(
    *,
    existing_ils: list[Any],
    existing_labor: list[Any],
    existing_findings: list[Any],
    snapshot: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], Any]:
    """Ключ отсутствует → не трогать; ключ есть (в т.ч. []/None) → явное значение + merge."""
    from sfrfr.services.period_date_correction import (
        mark_dependents_needs_recheck,
        merge_periods_preserve_corrections,
    )

    ils_in = snapshot["ils_periods"] if "ils_periods" in snapshot else _MISSING
    labor_in = snapshot["labor_periods"] if "labor_periods" in snapshot else _MISSING
    findings_in = snapshot["findings"] if "findings" in snapshot else _MISSING
    draft_in = snapshot["draft"] if "draft" in snapshot else _MISSING

    if ils_in is _MISSING:
        ils_out = [dict(x) for x in existing_ils if isinstance(x, dict)]
    else:
        ils_out = merge_periods_preserve_corrections(
            existing=existing_ils,
            incoming=ils_in if isinstance(ils_in, list) else [],
        )

    if labor_in is _MISSING:
        labor_out = [dict(x) for x in existing_labor if isinstance(x, dict)]
    else:
        labor_out = merge_periods_preserve_corrections(
            existing=existing_labor,
            incoming=labor_in if isinstance(labor_in, list) else [],
        )

    has_correction = any(
        isinstance(p, dict) and p.get("staff_date_correction") for p in ils_out + labor_out
    )
    if findings_in is _MISSING:
        findings_out = [dict(x) for x in existing_findings if isinstance(x, dict)]
    else:
        findings_out = (
            [dict(x) for x in findings_in if isinstance(x, dict)]
            if isinstance(findings_in, list)
            else []
        )
        if has_correction:
            findings_out = mark_dependents_needs_recheck(findings_out)

    draft_out: Any
    if draft_in is _MISSING:
        draft_out = _MISSING
    else:
        draft_out = draft_in
        if has_correction and isinstance(draft_out, dict):
            draft_out = dict(draft_out)
            draft_out.pop("recalculated", None)
            draft_out["dependents_status"] = "needs_recheck"

    return ils_out, labor_out, findings_out, draft_out


def database_reachable(dsn: str | None = None, timeout_sec: float = 2.0) -> bool:
    """Короткий probe: не использовать production; только для skip integration."""
    settings = get_settings()
    url = _psycopg_dsn(dsn or settings.database_url)
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    # Защита: не считать cloud-prod «тестовой БД» без явного local/test маркера.
    if host not in {"127.0.0.1", "localhost"} and "test" not in host:
        return False
    try:
        with psycopg.connect(url, connect_timeout=timeout_sec) as conn:
            with conn.cursor() as cur:
                cur.execute("select 1")
                cur.fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False
