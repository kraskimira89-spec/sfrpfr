"""Тесты lookup staff_roles без maybe_single (пустой ответ)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

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
