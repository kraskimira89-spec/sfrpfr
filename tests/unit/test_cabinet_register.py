"""Саморегистрация клиента: почта и телефон обязательны."""

from __future__ import annotations

from fastapi.testclient import TestClient

from sfrfr.api import create_app

_OK = {
    "email": "client@example.com",
    "phone": "+7 (909) 195-04-08",
    "consent": True,
}


def test_cabinet_register_requires_email_and_phone() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/portal/auth/register",
        json=_OK,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["email"] == "client@example.com"
    assert body["phone"] == "+79091950408"


def test_cabinet_register_rejects_missing_consent() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/portal/auth/register",
        json={**_OK, "consent": False},
    )
    assert response.status_code == 400
    assert "СОПД" in response.json()["detail"]


def test_cabinet_register_rejects_bad_email() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/portal/auth/register",
        json={**_OK, "email": "not-an-email"},
    )
    assert response.status_code == 400
    assert "почт" in response.json()["detail"].lower()


def test_cabinet_register_rejects_bad_phone() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/portal/auth/register",
        json={**_OK, "phone": "12345"},
    )
    assert response.status_code in {400, 422}


def test_cabinet_register_rejects_missing_phone() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/portal/auth/register",
        json={"email": "a@b.co", "consent": True},
    )
    assert response.status_code == 422


def test_cabinet_register_rejects_missing_email() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/portal/auth/register",
        json={"phone": "+79091112233", "consent": True},
    )
    assert response.status_code == 422
