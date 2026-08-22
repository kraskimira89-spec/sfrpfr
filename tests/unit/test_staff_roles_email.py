"""Тесты staff_roles: вход по staff_email без list_users."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfrfr.db.staff_roles import get_staff_role_by_email
from sfrfr.security.auth import StaffRole


def test_get_staff_role_by_email_from_staff_email_column() -> None:
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    table.execute.return_value = MagicMock(
        data=[{"user_id": "uid-1", "role": "admin", "staff_email": "info@example.ru"}]
    )
    client = MagicMock()
    client.table.return_value = table

    with patch("sfrfr.db.staff_roles.get_supabase_client", return_value=client):
        role = get_staff_role_by_email("info@example.ru")

    assert role is StaffRole.ADMIN
    client.auth.admin.list_users.assert_not_called()
