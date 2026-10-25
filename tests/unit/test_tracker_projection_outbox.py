"""Outbox проекции дела → Трекер: идемпотентность и outcome_unknown."""

from __future__ import annotations

import json

import httpx
import pytest

from sfrfr.integrations.yandex_tracker.client import TrackerClient
from sfrfr.integrations.yandex_tracker.outbox import (
    InMemoryTrackerOutboxStore,
    enqueue_projection_event,
    process_tracker_outbox,
)
from sfrfr.integrations.yandex_tracker.projection import (
    CaseProjection,
    build_tracker_fields,
    sync_case_projection,
)

FIELD_IDS = {
    "case_ref": "caseRef",
    "current_stage": "currentStage",
    "case_revision": "caseRevision",
    "next_action": "nextAction",
    "waiting_on": "waitingOn",
    "sync_status": "syncStatus",
    "analysis_payment": "analysisPayment",
    "appeals_payment": "appealsPayment",
    "escalation_payment": "escalationPayment",
}


def _make_handler(*, fail_patch: bool = False, remote_revision: int | None = None):
    state = {"version": 3}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and "/issues/" in request.url.path:
            body: dict = {"key": "CASE-42", "version": state["version"]}
            if remote_revision is not None:
                body["caseRevision"] = remote_revision
            return httpx.Response(200, json=body)
        if request.method == "PATCH":
            if fail_patch:
                return httpx.Response(503, json={"errorMessages": ["down"]})
            payload = json.loads(request.content.decode())
            assert payload.get("analysisPayment") == "paid"
            assert "status" not in payload
            state["version"] += 1
            return httpx.Response(
                200,
                json={"key": "CASE-42", "version": state["version"], **payload},
            )
        return httpx.Response(404)

    return handler


def test_build_tracker_fields_maps_ids() -> None:
    fields = build_tracker_fields(
        CaseProjection(
            case_ref="abc123",
            case_revision=5,
            current_stage="full_analysis",
            next_action="Подготовить анализ",
            waiting_on="staff",
            analysis_payment="paid",
        ),
        FIELD_IDS,
    )
    assert fields["caseRef"] == "abc123"
    assert fields["currentStage"] == "full_analysis"
    assert fields["analysisPayment"] == "paid"


@pytest.mark.asyncio
async def test_outbox_payment_confirmed_updates_projection() -> None:
    store = InMemoryTrackerOutboxStore()
    enqueue_projection_event(
        store,
        event_id="evt-pay-1",
        event_type="payment_confirmed",
        case_ref="abc123",
        issue_key="CASE-42",
        case_revision=5,
        payload={
            "current_stage": "full_analysis",
            "next_action": "Подготовить подробный анализ",
            "waiting_on": "staff",
            "analysis_payment": "paid",
            "appeals_payment": "not_ordered",
            "escalation_payment": "not_ordered",
            "sync_status": "ok",
        },
    )
    # повтор того же event_id
    enqueue_projection_event(
        store,
        event_id="evt-pay-1",
        event_type="payment_confirmed",
        case_ref="abc123",
        issue_key="CASE-42",
        case_revision=5,
        payload={
            "current_stage": "full_analysis",
            "next_action": "Подготовить подробный анализ",
            "waiting_on": "staff",
            "analysis_payment": "paid",
            "appeals_payment": "not_ordered",
            "escalation_payment": "not_ordered",
            "sync_status": "ok",
        },
    )
    assert len(store.list_pending(limit=10)) == 1

    transport = httpx.MockTransport(_make_handler())
    async with TrackerClient(
        oauth_token="t",
        organization_id="o",
        organization_header="X-Org-ID",
        transport=transport,
    ) as client:
        stats = await process_tracker_outbox(store, client, field_ids=FIELD_IDS)

    assert stats["done"] == 1
    assert store.list_pending(limit=10) == []


@pytest.mark.asyncio
async def test_outbox_conflict_on_same_id_different_body() -> None:
    store = InMemoryTrackerOutboxStore()
    enqueue_projection_event(
        store,
        event_id="evt-x",
        event_type="payment_confirmed",
        case_ref="a",
        issue_key="CASE-1",
        case_revision=1,
        payload={"current_stage": "documents", "next_action": "a", "waiting_on": "staff"},
    )
    with pytest.raises(ValueError, match="conflict"):
        enqueue_projection_event(
            store,
            event_id="evt-x",
            event_type="payment_confirmed",
            case_ref="a",
            issue_key="CASE-1",
            case_revision=2,
            payload={"current_stage": "documents", "next_action": "b", "waiting_on": "staff"},
        )


@pytest.mark.asyncio
async def test_outcome_unknown_keeps_pending() -> None:
    store = InMemoryTrackerOutboxStore()
    enqueue_projection_event(
        store,
        event_id="evt-500",
        event_type="payment_confirmed",
        case_ref="abc",
        issue_key="CASE-42",
        case_revision=1,
        payload={
            "current_stage": "full_analysis",
            "next_action": "x",
            "waiting_on": "staff",
            "analysis_payment": "paid",
        },
    )
    transport = httpx.MockTransport(_make_handler(fail_patch=True))
    async with TrackerClient(
        oauth_token="t",
        organization_id="o",
        organization_header="X-Org-ID",
        transport=transport,
    ) as client:
        stats = await process_tracker_outbox(store, client, field_ids=FIELD_IDS)
    assert stats["retry"] == 1
    assert len(store.list_pending(limit=5)) == 1


@pytest.mark.asyncio
async def test_skip_when_remote_revision_newer() -> None:
    projection = CaseProjection(
        case_ref="abc",
        case_revision=3,
        current_stage="documents",
        next_action="ждём",
        waiting_on="client",
        analysis_payment="paid",
    )
    transport = httpx.MockTransport(_make_handler(remote_revision=5))
    async with TrackerClient(
        oauth_token="t",
        organization_id="o",
        organization_header="X-Org-ID",
        transport=transport,
    ) as client:
        result = await sync_case_projection(
            client,
            issue_key="CASE-42",
            field_ids=FIELD_IDS,
            projection=projection,
        )
    assert result.ok and result.skipped
