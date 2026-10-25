"""TDD: inbox webhook → claim → применение рабочего статуса Трекера."""

from __future__ import annotations

import hashlib
import json
from uuid import uuid4

import httpx
import pytest

from sfrfr.integrations.yandex_tracker.client import TrackerClient
from sfrfr.integrations.yandex_tracker.inbox import (
    InMemoryTrackerInboxStore,
    InMemoryTrackerSyncStateStore,
    accept_tracker_webhook,
    apply_tracker_snapshot,
    process_tracker_inbox,
)


ORG = "org-1"
FIELD_STATUS = "status"


def _payload_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def test_accept_webhook_dedupes_same_payload() -> None:
    store = InMemoryTrackerInboxStore()
    body = {
        "schema_version": 1,
        "issue_key": "CASE-1",
        "issue_id": "tid-1",
        "command_id": "cmd-1",
        "command_type": "signal_reread",
        "event_kind": "issue_updated",
    }
    a = accept_tracker_webhook(
        store,
        organization_id=ORG,
        tracker_issue_id="tid-1",
        event_kind="issue_updated",
        dedupe_key=f"{ORG}:cmd-1",
        payload=body,
    )
    b = accept_tracker_webhook(
        store,
        organization_id=ORG,
        tracker_issue_id="tid-1",
        event_kind="issue_updated",
        dedupe_key=f"{ORG}:cmd-1",
        payload=body,
    )
    assert a.duplicate is False
    assert b.duplicate is True
    assert a.inbox_id == b.inbox_id
    assert store.count() == 1


def test_accept_webhook_conflict_on_same_key_different_body() -> None:
    store = InMemoryTrackerInboxStore()
    accept_tracker_webhook(
        store,
        organization_id=ORG,
        tracker_issue_id="tid-1",
        event_kind="issue_updated",
        dedupe_key=f"{ORG}:cmd-x",
        payload={"schema_version": 1, "v": 1},
    )
    with pytest.raises(ValueError, match="conflict"):
        accept_tracker_webhook(
            store,
            organization_id=ORG,
            tracker_issue_id="tid-1",
            event_kind="issue_updated",
            dedupe_key=f"{ORG}:cmd-x",
            payload={"schema_version": 1, "v": 2},
        )


@pytest.mark.asyncio
async def test_process_applies_newer_tracker_version_only() -> None:
    inbox = InMemoryTrackerInboxStore()
    state = InMemoryTrackerSyncStateStore()
    binding_id = state.ensure_binding(
        organization_id=ORG,
        tracker_issue_id="tid-9",
        tracker_issue_key="CASE-9",
        case_id=str(uuid4()),
        binding_kind="case_root",
        purpose_key="root",
    )
    state.set_tracker_version(binding_id, 10, status_key="open")

    accept_tracker_webhook(
        inbox,
        organization_id=ORG,
        tracker_issue_id="tid-9",
        event_kind="issue_updated",
        dedupe_key=f"{ORG}:evt-11",
        payload={"schema_version": 1, "issue_key": "CASE-9"},
        source_version=11,
        binding_id=binding_id,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "key": "CASE-9",
                "id": "tid-9",
                "version": 11,
                "status": {"key": "inProgress", "display": "В работе"},
            },
        )

    transport = httpx.MockTransport(handler)
    async with TrackerClient(
        oauth_token="t",
        organization_id="o",
        organization_header="X-Org-ID",
        transport=transport,
    ) as client:
        stats = await process_tracker_inbox(inbox, state, client, organization_id=ORG)

    assert stats["processed"] == 1
    assert stats["applied"] == 1
    snap = state.get_task_state(binding_id)
    assert snap is not None
    assert snap.tracker_version == 11
    assert snap.tracker_status_key == "inProgress"
    assert snap.app_stage_id is None  # webhook не двигает этап дела
    assert len(state.history_for(binding_id)) == 1


@pytest.mark.asyncio
async def test_older_version_is_ignored() -> None:
    inbox = InMemoryTrackerInboxStore()
    state = InMemoryTrackerSyncStateStore()
    binding_id = state.ensure_binding(
        organization_id=ORG,
        tracker_issue_id="tid-9",
        tracker_issue_key="CASE-9",
        case_id=str(uuid4()),
        binding_kind="case_root",
        purpose_key="root",
    )
    state.set_tracker_version(binding_id, 13, status_key="inProgress")

    accept_tracker_webhook(
        inbox,
        organization_id=ORG,
        tracker_issue_id="tid-9",
        event_kind="issue_updated",
        dedupe_key=f"{ORG}:evt-old",
        payload={"schema_version": 1},
        binding_id=binding_id,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "key": "CASE-9",
                "id": "tid-9",
                "version": 12,
                "status": {"key": "open"},
            },
        )

    transport = httpx.MockTransport(handler)
    async with TrackerClient(
        oauth_token="t",
        organization_id="o",
        organization_header="X-Org-ID",
        transport=transport,
    ) as client:
        stats = await process_tracker_inbox(inbox, state, client, organization_id=ORG)

    assert stats["ignored"] == 1
    assert state.get_task_state(binding_id).tracker_version == 13


@pytest.mark.asyncio
async def test_apply_snapshot_rejects_payment_confirmation_fields() -> None:
    state = InMemoryTrackerSyncStateStore()
    binding_id = state.ensure_binding(
        organization_id=ORG,
        tracker_issue_id="tid-1",
        tracker_issue_key="CASE-1",
        case_id=str(uuid4()),
        binding_kind="case_root",
        purpose_key="root",
    )
    result = apply_tracker_snapshot(
        state,
        binding_id=binding_id,
        tracker_version=2,
        tracker_status_key="closed",
        forbidden_hints={"payment_confirmed": True},
    )
    assert result.rejected is True
    assert state.get_task_state(binding_id) is None or (
        state.get_task_state(binding_id).tracker_version != 2
    )
