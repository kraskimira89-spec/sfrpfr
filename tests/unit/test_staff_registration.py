"""Заявки на доступ сотрудника: подпись, создание, модерация."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from sfrfr.db.staff_registration import (
    create_registration_request,
    moderate_registration_request,
    staff_reg_sig,
    verify_staff_reg_sig,
)


def test_staff_reg_sig_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLIC_LEAD_TOKEN", "test-secret")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    sig = staff_reg_sig("req-1", "approved")
    assert verify_staff_reg_sig("req-1", "approved", sig)
    assert not verify_staff_reg_sig("req-1", "rejected", sig)


def test_create_registration_request_validates_email(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as exc:
        create_registration_request(email="bad", display_name="Иван И.")
    assert exc.value.status_code == 400


def test_create_registration_request_duplicate_staff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sfrfr.db.staff_registration.get_staff_row_by_email",
        lambda _email: {"status": "active"},
    )
    monkeypatch.setattr(
        "sfrfr.db.staff_registration.get_pending_by_email",
        lambda _email: None,
    )
    with pytest.raises(HTTPException) as exc:
        create_registration_request(email="ops@test.ru", display_name="Иван И.")
    assert exc.value.status_code == 409


def test_create_registration_request_inserts_and_notifies(monkeypatch: pytest.MonkeyPatch) -> None:
    table = MagicMock()
    table.insert.return_value.execute.return_value.data = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "email": "new@test.ru",
            "display_name": "Новый С.",
            "status": "pending",
        }
    ]
    client = MagicMock()
    client.table.return_value = table
    monkeypatch.setattr("sfrfr.db.staff_registration.get_supabase_client", lambda: client)
    monkeypatch.setattr("sfrfr.db.staff_registration.get_staff_row_by_email", lambda _e: None)
    monkeypatch.setattr("sfrfr.db.staff_registration.get_pending_by_email", lambda _e: None)
    notified: list[dict] = []
    monkeypatch.setattr(
        "sfrfr.db.staff_registration.notify_staff_registration_queued",
        lambda row: notified.append(row) or {"email": {"ok": True}},
    )

    result = create_registration_request(email="new@test.ru", display_name="Новый С.")
    assert result["ok"] is True
    assert notified
    client.table.assert_called_with("staff_registration_requests")


def test_moderate_reject_updates_status(monkeypatch: pytest.MonkeyPatch) -> None:
    table = MagicMock()
    table.update.return_value.eq.return_value.execute.return_value = None
    client = MagicMock()
    client.table.return_value = table
    monkeypatch.setattr("sfrfr.db.staff_registration.get_supabase_client", lambda: client)
    monkeypatch.setattr(
        "sfrfr.db.staff_registration.get_request",
        lambda _id: {
            "id": "11111111-1111-1111-1111-111111111111",
            "email": "new@test.ru",
            "display_name": "Новый С.",
            "status": "pending",
        },
    )

    result = moderate_registration_request(
        "11111111-1111-1111-1111-111111111111",
        action="rejected",
    )
    assert result["status"] == "rejected"
    table.update.assert_called_once()


def test_moderate_approve_invites_staff(monkeypatch: pytest.MonkeyPatch) -> None:
    table = MagicMock()
    table.update.return_value.eq.return_value.execute.return_value = None
    client = MagicMock()
    client.table.return_value = table
    monkeypatch.setattr("sfrfr.db.staff_registration.get_supabase_client", lambda: client)
    monkeypatch.setattr(
        "sfrfr.db.staff_registration.get_request",
        lambda _id: {
            "id": "11111111-1111-1111-1111-111111111111",
            "email": "new@test.ru",
            "display_name": "Новый С.",
            "status": "pending",
        },
    )
    invited: list[dict] = []
    monkeypatch.setattr(
        "sfrfr.db.staff_registration.invite_staff_member",
        lambda **kwargs: invited.append(kwargs) or {"user_id": "u1"},
    )

    result = moderate_registration_request(
        "11111111-1111-1111-1111-111111111111",
        action="approved",
    )
    assert result["status"] == "approved"
    assert invited[0]["email"] == "new@test.ru"
    assert invited[0]["role"] == "operator"
