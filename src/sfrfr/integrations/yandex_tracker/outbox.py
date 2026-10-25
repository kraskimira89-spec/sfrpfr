"""Outbox синхронизации проекции дела → Трекер.

Событие пишется после бизнес-факта; ошибка Трекера не откатывает оплату.
Worker не делает слепой retry create: при outcome_unknown оставляет pending.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from sfrfr.integrations.yandex_tracker.client import TrackerClient
from sfrfr.integrations.yandex_tracker.projection import (
    projection_from_payload,
    sync_case_projection,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TrackerOutboxEvent:
    event_id: str
    event_type: str
    case_ref: str
    issue_key: str
    case_revision: int
    payload: dict[str, Any]
    case_id: str | None = None
    status: str = "pending"
    attempts: int = 0
    last_error: str | None = None
    origin: str = "app"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    processed_at: datetime | None = None


class TrackerOutboxStore(Protocol):
    def enqueue(self, event: TrackerOutboxEvent) -> TrackerOutboxEvent:
        """Идемпотентно по event_id: повтор с тем же телом — ok; конфликт тела — ошибка."""

    def list_pending(self, *, limit: int) -> list[TrackerOutboxEvent]: ...

    def mark_done(
        self,
        event_id: str,
        *,
        tracker_version: int | None,
    ) -> None: ...

    def mark_retry(self, event_id: str, error: str) -> None: ...

    def mark_error(self, event_id: str, error: str) -> None: ...


class InMemoryTrackerOutboxStore:
    """Для unit-тестов и локального dry-run без БД."""

    def __init__(self) -> None:
        self._by_id: dict[str, TrackerOutboxEvent] = {}

    def enqueue(self, event: TrackerOutboxEvent) -> TrackerOutboxEvent:
        existing = self._by_id.get(event.event_id)
        if existing is None:
            self._by_id[event.event_id] = event
            return event
        if (
            existing.event_type == event.event_type
            and existing.case_ref == event.case_ref
            and existing.issue_key == event.issue_key
            and existing.case_revision == event.case_revision
            and existing.payload == event.payload
        ):
            return existing
        raise ValueError("tracker_outbox_event_conflict")

    def list_pending(self, *, limit: int) -> list[TrackerOutboxEvent]:
        items = [e for e in self._by_id.values() if e.status == "pending"]
        items.sort(key=lambda e: e.created_at)
        return items[:limit]

    def mark_done(self, event_id: str, *, tracker_version: int | None) -> None:
        ev = self._by_id[event_id]
        ev.status = "done"
        ev.processed_at = datetime.now(UTC)
        ev.last_error = None
        if tracker_version is not None:
            ev.payload = {**ev.payload, "last_observed_tracker_version": tracker_version}

    def mark_retry(self, event_id: str, error: str) -> None:
        ev = self._by_id[event_id]
        ev.attempts += 1
        ev.last_error = error[:300]
        # остаётся pending — сверка при следующем тике

    def mark_error(self, event_id: str, error: str) -> None:
        ev = self._by_id[event_id]
        ev.attempts += 1
        ev.last_error = error[:300]
        ev.status = "error"


def enqueue_projection_event(
    store: TrackerOutboxStore,
    *,
    event_id: str,
    event_type: str,
    case_ref: str,
    issue_key: str,
    case_revision: int,
    payload: Mapping[str, Any],
    case_id: str | None = None,
) -> TrackerOutboxEvent:
    body = dict(payload)
    body.setdefault("case_ref", case_ref)
    body.setdefault("case_revision", case_revision)
    return store.enqueue(
        TrackerOutboxEvent(
            event_id=event_id,
            event_type=event_type,
            case_ref=case_ref,
            issue_key=issue_key,
            case_revision=case_revision,
            payload=body,
            case_id=case_id,
            origin="app",
        )
    )


async def process_tracker_outbox(
    store: TrackerOutboxStore,
    client: TrackerClient,
    *,
    field_ids: Mapping[str, str],
    limit: int = 20,
) -> dict[str, int]:
    """Обработать pending-события проекции. Не создаёт inbox-команды."""
    stats = {"processed": 0, "done": 0, "retry": 0, "error": 0, "skipped": 0}
    for event in store.list_pending(limit=limit):
        stats["processed"] += 1
        projection = projection_from_payload(event.payload)
        result = await sync_case_projection(
            client,
            issue_key=event.issue_key,
            field_ids=field_ids,
            projection=projection,
        )
        if result.ok:
            store.mark_done(event.event_id, tracker_version=result.tracker_version)
            stats["done"] += 1
            if result.skipped:
                stats["skipped"] += 1
            continue
        if result.outcome_unknown:
            store.mark_retry(event.event_id, result.reason or "outcome_unknown")
            stats["retry"] += 1
            logger.warning(
                "tracker_outbox_outcome_unknown event_id=%s issue=%s",
                event.event_id[:16],
                event.issue_key,
            )
            continue
        store.mark_error(event.event_id, result.reason or "sync_failed")
        stats["error"] += 1
    return stats
