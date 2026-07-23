"""Тесты health/ops и redaction логов (ТЗ-05)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from sfrfr.api import create_app
from sfrfr.core.config import get_settings
from sfrfr.ops.health import public_health_payload
from sfrfr.ops.logging import redact_log_text


def test_redact_log_text_masks_snils_and_token() -> None:
    text = (
        "user Иванов Иван Иванович snils 123-456-789 00 "
        "Authorization: Bearer super-secret-token "
        "url?access_token=abc123&x=1"
    )
    out = redact_log_text(text)
    assert "123-456-789 00" not in out
    assert "super-secret-token" not in out
    assert "abc123" not in out
    assert "***" in out


def test_public_health_has_no_pii_keys() -> None:
    payload = public_health_payload()
    blob = str(payload).lower()
    assert payload["status"] == "ok"
    assert "snils" not in blob
    assert "full_name" not in blob
    assert "service_role" not in blob


def test_health_endpoint_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "checks" in data


def test_docs_open_without_auth() -> None:
    client = TestClient(create_app())
    response = client.get("/docs")
    assert response.status_code == 200


def test_ops_status_requires_token(monkeypatch) -> None:
    monkeypatch.setenv("OPS_MONITOR_TOKEN", "secret-ops-token")
    monkeypatch.setenv("OPS_FAILED_ALERT_THRESHOLD", "1")
    get_settings.cache_clear()
    client = TestClient(create_app())
    denied = client.get("/ops/status")
    assert denied.status_code == 401
    ok = client.get("/ops/status", headers={"X-Ops-Token": "secret-ops-token"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] == "ok"
    assert "failed_cases" in body["monitor"]
    get_settings.cache_clear()
