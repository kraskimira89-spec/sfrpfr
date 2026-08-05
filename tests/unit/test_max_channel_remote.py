"""Тест ops-эндпоинта channel-ids."""

from __future__ import annotations

from fastapi.testclient import TestClient

from sfrfr.api import create_app
from sfrfr.core.config import get_settings


def test_channel_ids_requires_auth(monkeypatch) -> None:
    monkeypatch.setenv("OPS_MONITOR_TOKEN", "ops-secret")
    monkeypatch.setenv("MAX_WEBHOOK_SECRET", "")
    get_settings.cache_clear()
    client = TestClient(create_app())
    assert client.get("/api/integrations/max/channel-ids").status_code == 401
    ok = client.get(
        "/api/integrations/max/channel-ids",
        headers={"X-Ops-Token": "ops-secret"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["ok"] is True
    assert "discovered" in body
    get_settings.cache_clear()
