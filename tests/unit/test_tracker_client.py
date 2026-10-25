"""TDD: транспортный TrackerClient без retry-циклов на write."""

from __future__ import annotations

import json

import httpx
import pytest

from sfrfr.integrations.yandex_tracker.client import TrackerClient, TrackerError


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if request.method == "GET" and path.endswith("/issues/CASE-1"):
        return httpx.Response(
            200,
            json={"key": "CASE-1", "version": 7, "status": {"key": "open"}},
        )
    if request.method == "PATCH" and path.endswith("/issues/CASE-1"):
        assert request.url.params.get("version") == "7"
        body = json.loads(request.content.decode())
        assert "status" not in body
        return httpx.Response(200, json={"key": "CASE-1", "version": 8, **body})
    if request.method == "GET" and path.endswith("/transitions"):
        return httpx.Response(
            200,
            json=[{"id": "start_progress", "display": "В работу"}],
        )
    if request.method == "POST" and "/transitions/start_progress/_execute" in path:
        return httpx.Response(200, json={"key": "CASE-1"})
    if request.method == "PATCH" and path.endswith("/issues/CASE-500"):
        return httpx.Response(500, json={"errorMessages": ["boom"]})
    return httpx.Response(404, json={"errorMessages": ["missing"]})


@pytest.mark.asyncio
async def test_get_issue_and_update_fields() -> None:
    transport = httpx.MockTransport(_handler)
    async with TrackerClient(
        oauth_token="token",
        organization_id="org",
        organization_header="X-Org-ID",
        transport=transport,
    ) as client:
        issue = await client.get_issue("CASE-1")
        assert issue["version"] == 7
        updated = await client.update_fields(
            "CASE-1",
            {"customField": "full_analysis"},
            version=7,
        )
        assert updated["version"] == 8


@pytest.mark.asyncio
async def test_update_fields_rejects_status() -> None:
    transport = httpx.MockTransport(_handler)
    async with TrackerClient(
        oauth_token="token",
        organization_id="org",
        organization_header="X-Org-ID",
        transport=transport,
    ) as client:
        with pytest.raises(ValueError, match="execute_transition"):
            await client.update_fields("CASE-1", {"status": "closed"}, version=1)


@pytest.mark.asyncio
async def test_write_500_is_outcome_unknown() -> None:
    transport = httpx.MockTransport(_handler)
    async with TrackerClient(
        oauth_token="token",
        organization_id="org",
        organization_header="X-Org-ID",
        transport=transport,
    ) as client:
        with pytest.raises(TrackerError) as exc:
            await client.update_fields("CASE-500", {"x": 1}, version=1)
        assert exc.value.outcome_unknown is True
        assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_transitions() -> None:
    transport = httpx.MockTransport(_handler)
    async with TrackerClient(
        oauth_token="token",
        organization_id="org",
        organization_header="X-Org-ID",
        transport=transport,
    ) as client:
        items = await client.get_transitions("CASE-1")
        assert items[0]["id"] == "start_progress"
        await client.execute_transition("CASE-1", "start_progress")
