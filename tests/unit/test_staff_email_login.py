"""Precheck входа сотрудника по e-mail OTP."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from sfrfr.api import create_app
from sfrfr.services.staff_email_login import (
    prepare_staff_email_otp,
    staff_email_login_allowed,
)


def test_staff_email_login_allowed_requires_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sfrfr.services.staff_email_login.get_staff_role_by_email",
        lambda _email: None,
    )
    allowed, reason = staff_email_login_allowed("unknown@test.ru")
    assert allowed is False
    assert reason == "no_staff_role"


def test_staff_email_login_allowed_requires_auth_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sfrfr.services.staff_email_login.get_staff_role_by_email",
        lambda _email: "admin",
    )
    monkeypatch.setattr(
        "sfrfr.services.staff_email_login._auth_user_ready",
        lambda _email: False,
    )
    allowed, reason = staff_email_login_allowed("staff@test.ru")
    assert allowed is False
    assert reason == "no_auth_user"


def test_prepare_staff_email_otp_notifies_admin_when_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sfrfr.services.staff_email_login.staff_email_login_allowed",
        lambda _email: (False, "no_staff_role"),
    )
    notify = MagicMock(return_value={"email": {"ok": True}})
    monkeypatch.setattr(
        "sfrfr.services.staff_email_login.notify_staff_login_blocked",
        notify,
    )
    result = prepare_staff_email_otp("unknown@test.ru")
    assert result["allowed"] is False
    assert "proverkastaza@yandex.ru" in result["message"]
    notify.assert_called_once_with(email="unknown@test.ru", reason="no_staff_role")


def test_staff_email_otp_request_endpoint_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sfrfr.services.staff_email_login.prepare_staff_email_otp",
        lambda _email: {
            "ok": True,
            "allowed": True,
            "message": "Код можно отправить на рабочую почту.",
        },
    )
    client = TestClient(create_app())
    response = client.post(
        "/api/portal/auth/staff/email-otp/request",
        json={"email": "staff@test.ru"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["allowed"] is True


def test_staff_email_otp_request_endpoint_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sfrfr.services.staff_email_login.prepare_staff_email_otp",
        lambda _email: {
            "ok": True,
            "allowed": False,
            "reason": "no_staff_role",
            "message": "Обратитесь к администратору.",
        },
    )
    client = TestClient(create_app())
    response = client.post(
        "/api/portal/auth/staff/email-otp/request",
        json={"email": "unknown@test.ru"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["allowed"] is False
    assert body["reason"] == "no_staff_role"
