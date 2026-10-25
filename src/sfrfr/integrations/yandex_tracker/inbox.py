"""Входящий контур: webhook → inbox → снимок рабочего статуса Трекера.

Не подтверждает оплату, доставку и подачу. Этап дела (13 ступеней)
не меняется из статуса задачи.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import uuid4

from sfrfr.integrations.yandex_tracker.client import TrackerClient, TrackerError

logger = logging.getLogger(__name__)


def payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class InboxRecord:
    id: str
    organization_id: str
    tracker_issue_id: str
    event_kind: str
    dedupe_key: str
    payload_hash: str
    payload: dict[str, Any]
    state: str = "pending"
    attempts: int = 0
    available_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    lease_token: str | None = None
    lease_until: datetime | None = None
    binding_id: str | None = None
    source_event_id: str | None = None
    source_version: int | None = None
    duplicate_count: int = 0
    received_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_received_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    last_error_code: str | None = None


@dataclass(frozen=True, slots=True)
class AcceptResult:
    inbox_id: str
    duplicate: bool
    conflict: bool = False


@dataclass(slots=True)
class BindingRecord:
    id: str
    organization_id: str
    tracker_issue_id: str
    tracker_issue_key: str
    case_id: str
    binding_kind: str
    purpose_key: str
    enabled: bool = True


@dataclass(slots=True)
class TaskStateRecord:
    binding_id: str
    tracker_status_key: str | None = None
    tracker_version: int | None = None
    app_stage_id: str | None = None
    app_revision: int = 0
    local_revision: int = 0
    projected_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ApplyResult:
    applied: bool = False
    ignored: bool = False
    rejected: bool = False
    reason: str | None = None
    local_revision: int | None = None


class TrackerInboxStore(Protocol):
    def accept(
        self,
        *,
        organization_id: str,
        tracker_issue_id: str,
        event_kind: str,
        dedupe_key: str,
        payload: dict[str, Any],
        source_event_id: str | None = None,
        source_version: int | None = None,
        binding_id: str | None = None,
    ) -> AcceptResult: ...

    def claim(self, *, lease_token: str, lease_seconds: int = 60) -> InboxRecord | None: ...

    def finish(
        self,
        inbox_id: str,
        *,
        lease_token: str,
        state: str,
        binding_id: str | None = None,
        error_code: str | None = None,
    ) -> bool: ...

    def mark_retry(
        self,
        inbox_id: str,
        *,
        lease_token: str,
        error_code: str,
        delay_seconds: int,
    ) -> bool: ...


class TrackerSyncStateStore(Protocol):
    def find_binding_by_issue_id(
        self, *, organization_id: str, tracker_issue_id: str
    ) -> BindingRecord | None: ...

    def get_task_state(self, binding_id: str) -> TaskStateRecord | None: ...

    def apply_tracker_status(
        self,
        *,
        binding_id: str,
        tracker_version: int,
        tracker_status_key: str,
        before: dict[str, Any],
        after: dict[str, Any],
        inbox_id: str | None,
        correlation_id: str,
    ) -> ApplyResult: ...


class InMemoryTrackerInboxStore:
    def __init__(self) -> None:
        self._by_id: dict[str, InboxRecord] = {}
        self._by_dedupe: dict[tuple[str, str], str] = {}

    def count(self) -> int:
        return len(self._by_id)

    def accept(
        self,
        *,
        organization_id: str,
        tracker_issue_id: str,
        event_kind: str,
        dedupe_key: str,
        payload: dict[str, Any],
        source_event_id: str | None = None,
        source_version: int | None = None,
        binding_id: str | None = None,
    ) -> AcceptResult:
        ph = payload_hash(payload)
        key = (organization_id, dedupe_key)
        existing_id = self._by_dedupe.get(key)
        if existing_id:
            row = self._by_id[existing_id]
            if row.payload_hash != ph:
                raise ValueError("tracker_inbox_payload_conflict")
            row.duplicate_count += 1
            row.last_received_at = datetime.now(UTC)
            return AcceptResult(inbox_id=row.id, duplicate=True)
        inbox_id = str(uuid4())
        row = InboxRecord(
            id=inbox_id,
            organization_id=organization_id,
            tracker_issue_id=tracker_issue_id,
            event_kind=event_kind,
            dedupe_key=dedupe_key,
            payload_hash=ph,
            payload=dict(payload),
            source_event_id=source_event_id,
            source_version=source_version,
            binding_id=binding_id,
        )
        self._by_id[inbox_id] = row
        self._by_dedupe[key] = inbox_id
        return AcceptResult(inbox_id=inbox_id, duplicate=False)

    def claim(self, *, lease_token: str, lease_seconds: int = 60) -> InboxRecord | None:
        now = datetime.now(UTC)
        candidates = [
            r
            for r in self._by_id.values()
            if r.state in {"pending", "retry"} and r.available_at <= now
        ]
        candidates.sort(key=lambda r: (r.available_at, r.received_at))
        if not candidates:
            return None
        row = candidates[0]
        row.state = "processing"
        row.attempts += 1
        row.lease_token = lease_token
        row.lease_until = now + timedelta(seconds=lease_seconds)
        return row

    def finish(
        self,
        inbox_id: str,
        *,
        lease_token: str,
        state: str,
        binding_id: str | None = None,
        error_code: str | None = None,
    ) -> bool:
        row = self._by_id.get(inbox_id)
        if row is None:
            return False
        if row.state != "processing" or row.lease_token != lease_token:
            return False
        if row.lease_until is None or row.lease_until < datetime.now(UTC):
            return False
        row.state = state
        row.lease_token = None
        row.lease_until = None
        row.finished_at = datetime.now(UTC)
        row.last_error_code = error_code
        if binding_id:
            row.binding_id = binding_id
        return True

    def mark_retry(
        self,
        inbox_id: str,
        *,
        lease_token: str,
        error_code: str,
        delay_seconds: int,
    ) -> bool:
        row = self._by_id.get(inbox_id)
        if row is None or row.lease_token != lease_token or row.state != "processing":
            return False
        row.state = "retry"
        row.lease_token = None
        row.lease_until = None
        row.last_error_code = error_code
        row.available_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
        return True


class InMemoryTrackerSyncStateStore:
    def __init__(self) -> None:
        self._bindings: dict[str, BindingRecord] = {}
        self._by_issue: dict[tuple[str, str], str] = {}
        self._state: dict[str, TaskStateRecord] = {}
        self._history: dict[str, list[dict[str, Any]]] = {}

    def ensure_binding(
        self,
        *,
        organization_id: str,
        tracker_issue_id: str,
        tracker_issue_key: str,
        case_id: str,
        binding_kind: str,
        purpose_key: str,
    ) -> str:
        key = (organization_id, tracker_issue_id)
        existing = self._by_issue.get(key)
        if existing:
            return existing
        binding_id = str(uuid4())
        self._bindings[binding_id] = BindingRecord(
            id=binding_id,
            organization_id=organization_id,
            tracker_issue_id=tracker_issue_id,
            tracker_issue_key=tracker_issue_key,
            case_id=case_id,
            binding_kind=binding_kind,
            purpose_key=purpose_key,
        )
        self._by_issue[key] = binding_id
        return binding_id

    def set_tracker_version(
        self, binding_id: str, version: int, *, status_key: str
    ) -> None:
        self._state[binding_id] = TaskStateRecord(
            binding_id=binding_id,
            tracker_version=version,
            tracker_status_key=status_key,
            local_revision=1,
        )

    def find_binding_by_issue_id(
        self, *, organization_id: str, tracker_issue_id: str
    ) -> BindingRecord | None:
        bid = self._by_issue.get((organization_id, tracker_issue_id))
        return self._bindings.get(bid) if bid else None

    def get_task_state(self, binding_id: str) -> TaskStateRecord | None:
        return self._state.get(binding_id)

    def history_for(self, binding_id: str) -> list[dict[str, Any]]:
        return list(self._history.get(binding_id, []))

    def apply_tracker_status(
        self,
        *,
        binding_id: str,
        tracker_version: int,
        tracker_status_key: str,
        before: dict[str, Any],
        after: dict[str, Any],
        inbox_id: str | None,
        correlation_id: str,
    ) -> ApplyResult:
        current = self._state.get(binding_id)
        if current and current.tracker_version is not None:
            if current.tracker_version >= tracker_version:
                return ApplyResult(ignored=True, reason="stale_or_same_version")
        local_rev = (current.local_revision if current else 0) + 1
        self._state[binding_id] = TaskStateRecord(
            binding_id=binding_id,
            tracker_status_key=tracker_status_key,
            tracker_version=tracker_version,
            app_stage_id=current.app_stage_id if current else None,
            app_revision=current.app_revision if current else 0,
            local_revision=local_rev,
            projected_fields=dict(current.projected_fields) if current else {},
        )
        self._history.setdefault(binding_id, []).append(
            {
                "local_revision": local_rev,
                "source": "tracker",
                "inbox_id": inbox_id,
                "correlation_id": correlation_id,
                "tracker_version": tracker_version,
                "before_state": before,
                "after_state": after,
                "reason_code": "tracker_snapshot_applied",
            }
        )
        return ApplyResult(applied=True, local_revision=local_rev)


def accept_tracker_webhook(
    store: TrackerInboxStore,
    *,
    organization_id: str,
    tracker_issue_id: str,
    event_kind: str,
    dedupe_key: str,
    payload: dict[str, Any],
    source_event_id: str | None = None,
    source_version: int | None = None,
    binding_id: str | None = None,
) -> AcceptResult:
    return store.accept(
        organization_id=organization_id,
        tracker_issue_id=tracker_issue_id,
        event_kind=event_kind,
        dedupe_key=dedupe_key,
        payload=payload,
        source_event_id=source_event_id,
        source_version=source_version,
        binding_id=binding_id,
    )


_FORBIDDEN_HINT_KEYS = frozenset(
    {
        "payment_confirmed",
        "payment_status",
        "submission_confirmed",
        "delivery_confirmed",
        "analysis_delivered",
    }
)


def apply_tracker_snapshot(
    state: TrackerSyncStateStore,
    *,
    binding_id: str,
    tracker_version: int,
    tracker_status_key: str,
    forbidden_hints: dict[str, Any] | None = None,
    inbox_id: str | None = None,
    correlation_id: str | None = None,
) -> ApplyResult:
    hints = forbidden_hints or {}
    if any(k in hints and hints[k] for k in _FORBIDDEN_HINT_KEYS):
        return ApplyResult(rejected=True, reason="forbidden_fact_from_tracker")
    current = state.get_task_state(binding_id)
    before = {
        "tracker_version": current.tracker_version if current else None,
        "tracker_status_key": current.tracker_status_key if current else None,
    }
    after = {
        "tracker_version": tracker_version,
        "tracker_status_key": tracker_status_key,
    }
    return state.apply_tracker_status(
        binding_id=binding_id,
        tracker_version=tracker_version,
        tracker_status_key=tracker_status_key,
        before=before,
        after=after,
        inbox_id=inbox_id,
        correlation_id=correlation_id or str(uuid4()),
    )


async def process_tracker_inbox(
    inbox: TrackerInboxStore,
    state: TrackerSyncStateStore,
    client: TrackerClient,
    *,
    organization_id: str,
    limit: int = 20,
) -> dict[str, int]:
    """Обработать pending/retry: GET issue → обновить только рабочий статус."""
    stats = {
        "processed": 0,
        "applied": 0,
        "ignored": 0,
        "rejected": 0,
        "retry": 0,
        "unbound": 0,
    }
    for _ in range(limit):
        lease = str(uuid4())
        row = inbox.claim(lease_token=lease)
        if row is None:
            break
        if row.organization_id != organization_id:
            inbox.finish(row.id, lease_token=lease, state="rejected", error_code="org_mismatch")
            stats["rejected"] += 1
            stats["processed"] += 1
            continue
        stats["processed"] += 1
        binding = state.find_binding_by_issue_id(
            organization_id=row.organization_id,
            tracker_issue_id=row.tracker_issue_id,
        )
        if binding is None or not binding.enabled:
            inbox.finish(row.id, lease_token=lease, state="ignored", error_code="no_binding")
            stats["unbound"] += 1
            stats["ignored"] += 1
            continue
        issue_key = str(row.payload.get("issue_key") or binding.tracker_issue_key)
        try:
            issue = await client.get_issue(issue_key)
        except TrackerError as exc:
            inbox.mark_retry(
                row.id,
                lease_token=lease,
                error_code=exc.reason,
                delay_seconds=min(300, 5 * (2 ** min(row.attempts, 5))),
            )
            stats["retry"] += 1
            continue

        version = int(issue.get("version") or 0)
        status_obj = issue.get("status") or {}
        status_key = str(status_obj.get("key") or "")
        hints = {
            k: row.payload.get(k)
            for k in _FORBIDDEN_HINT_KEYS
            if k in row.payload
        }
        result = apply_tracker_snapshot(
            state,
            binding_id=binding.id,
            tracker_version=version,
            tracker_status_key=status_key,
            forbidden_hints=hints,
            inbox_id=row.id,
        )
        if result.rejected:
            inbox.finish(
                row.id,
                lease_token=lease,
                state="rejected",
                binding_id=binding.id,
                error_code=result.reason,
            )
            stats["rejected"] += 1
            continue
        if result.ignored:
            inbox.finish(
                row.id,
                lease_token=lease,
                state="ignored",
                binding_id=binding.id,
                error_code=result.reason,
            )
            stats["ignored"] += 1
            continue
        inbox.finish(
            row.id,
            lease_token=lease,
            state="processed",
            binding_id=binding.id,
        )
        stats["applied"] += 1
    return stats
