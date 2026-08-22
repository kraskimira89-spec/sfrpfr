"""Тесты lookup staff_roles без maybe_single (пустой ответ)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sfrfr.security.auth import StaffRole, _lookup_role


def test_lookup_role_empty_list_is_none(monkeypatch) -> None:
    table = MagicMock()
    table.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
        SimpleNamespace(data=[])
    )
    client = MagicMock()
    client.table.return_value = table
    monkeypatch.setattr("sfrfr.security.auth.get_supabase_client", lambda: client)
    assert _lookup_role("user-without-role") is None


def test_lookup_role_returns_admin(monkeypatch) -> None:
    table = MagicMock()
    table.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
        SimpleNamespace(data=[{"role": "admin"}])
    )
    client = MagicMock()
    client.table.return_value = table
    monkeypatch.setattr("sfrfr.security.auth.get_supabase_client", lambda: client)
    assert _lookup_role("admin-user") is StaffRole.ADMIN


def test_lookup_role_falls_back_to_staff_email(monkeypatch) -> None:
    table = MagicMock()
    table.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
        SimpleNamespace(data=[])
    )
    client = MagicMock()
    client.table.return_value = table
    monkeypatch.setattr("sfrfr.security.auth.get_supabase_client", lambda: client)

    with (
        patch(
            "sfrfr.db.staff_roles.get_staff_role_by_email",
            return_value=StaffRole.ADMIN,
        ) as mock_role,
        patch("sfrfr.db.staff_roles.sync_staff_role_auth_user_id", return_value=True) as mock_sync,
    ):
        role = _lookup_role("jwt-user-new", "info@example.ru")

    assert role is StaffRole.ADMIN
    mock_role.assert_called_once_with("info@example.ru")
    mock_sync.assert_called_once_with(email="info@example.ru", auth_user_id="jwt-user-new")
