"""Тесты логирования auth и smoke portal OTP API."""

from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from sfrfr.api import create_app
from sfrfr.ops.auth_log import auth_event
from sfrfr.ops.logging import RedactingFilter, redact_log_text


def test_auth_event_logs_denied_as_warning(caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="sfrfr.auth.portal"):
        auth_event(
            "otp_verify",
            outcome="denied",
            status_code=400,
            detail="invalid or expired code",
            ticket="abcdefghijklmnop",
            reason="bad_code",
        )
    text = " ".join(r.message for r in caplog.records)
    assert "event=otp_verify" in text
    assert "outcome=denied" in text
    assert "ticket=abcdefgh…" in text
    assert "bad_code" in text


def test_redacting_filter_skips_uvicorn_access_args() -> None:
    """Access-лог uvicorn нельзя «сплющивать» — иначе AccessFormatter падает."""
    filt = RedactingFilter()
    args = ("127.0.0.1:1", "GET", "/api/portal/me", "1.1", 401)
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=args,
        exc_info=None,
    )
    assert filt.filter(record) is True
    assert record.args == args
    assert record.msg == '%s - "%s %s HTTP/%s" %d'


def test_redacting_filter_redacts_sfrfr_logger() -> None:
    filt = RedactingFilter()
    record = logging.LogRecord(
        name="sfrfr.auth.portal",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="token=abc123secret",
        args=(),
        exc_info=None,
    )
    assert filt.filter(record) is True
    assert "abc123secret" not in str(record.msg)



def test_redact_does_not_strip_portal_paths() -> None:
    raw = '109.252.100.99:0 - "POST /api/portal/auth/otp/request HTTP/1.1" 404'
    assert "/api/portal/auth/otp/request" in redact_log_text(raw)


def test_otp_request_client_pair_smoke(monkeypatch) -> None:
    from sfrfr.security import login_pending

    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-for-otp")
    # fresh in-memory pending store
    login_pending._BY_TICKET.clear()  # noqa: SLF001
    login_pending._BY_CODE.clear()  # noqa: SLF001
    login_pending._BY_MAX.clear()  # noqa: SLF001

    client = TestClient(create_app())
    response = client.post("/api/portal/auth/otp/request", json={"audience": "client"})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "pending_pair"
    assert body["ticket"]
    assert body["pair_code"]
    assert len(body["pair_code"]) == 6

    poll = client.get(f"/api/portal/auth/otp/poll?ticket={body['ticket']}")
    assert poll.status_code == 200
    assert poll.json()["status"] == "pending_pair"


def test_otp_verify_bad_code_is_400(monkeypatch) -> None:
    from sfrfr.security import login_pending

    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-for-otp")
    login_pending._BY_TICKET.clear()  # noqa: SLF001
    login_pending._BY_CODE.clear()  # noqa: SLF001
    login_pending._BY_MAX.clear()  # noqa: SLF001
    client = TestClient(create_app())
    started = client.post("/api/portal/auth/otp/request", json={}).json()
    response = client.post(
        "/api/portal/auth/otp/verify",
        json={"ticket": started["ticket"], "code": "000000"},
    )
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


def test_otp_poll_approved_after_bind(monkeypatch) -> None:
    """Симуляция: запрос кода → bind MAX → approve → poll отдаёт token_hash."""
    from sfrfr.security import login_pending

    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-for-otp")
    login_pending._BY_TICKET.clear()  # noqa: SLF001
    login_pending._BY_CODE.clear()  # noqa: SLF001
    login_pending._BY_MAX.clear()  # noqa: SLF001

    client = TestClient(create_app())
    started = client.post("/api/portal/auth/otp/request", json={}).json()
    ticket = started["ticket"]
    code = started["pair_code"]

    pending = login_pending.bind_max_by_code(
        pair_code=code,
        max_user_id="999001",
        contact="max_999001@clients.sfrfr.local",
    )
    assert pending is not None
    assert pending.status == "pending_confirm"

    approved = login_pending.approve(
        ticket_id=ticket,
        token_hash="hash-for-test",
        email="max_999001@clients.sfrfr.local",
    )
    assert approved is not None
    assert approved.status == "approved"

    poll = client.get(f"/api/portal/auth/otp/poll?ticket={ticket}")
    assert poll.status_code == 200
    body = poll.json()
    assert body["status"] == "approved"
    assert body["token_hash"] == "hash-for-test"
    assert body["email"] == "max_999001@clients.sfrfr.local"


def test_portal_me_requires_auth() -> None:
    client = TestClient(create_app())
    response = client.get("/api/portal/me")
    assert response.status_code in {401, 403}

