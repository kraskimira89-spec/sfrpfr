"""Синхронизация staff_roles.user_id с Supabase Auth."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfrfr.db.staff_roles import sync_staff_role_auth_user_id


def test_sync_staff_role_auth_user_id_updates_mismatch() -> None:
    table = MagicMock()
    table.update.return_value = table
    table.eq.return_value = table
    table.execute.return_value = MagicMock(data=[{"user_id": "new-uid"}])
    client = MagicMock()
    client.table.return_value = table

    with (
        patch("sfrfr.db.staff_roles.get_supabase_client", return_value=client),
        patch(
            "sfrfr.db.staff_roles._staff_row_by_email",
            return_value={"user_id": "old-uid", "role": "admin"},
        ),
    ):
        changed = sync_staff_role_auth_user_id(
            email="info@example.ru",
            auth_user_id="new-uid",
        )

    assert changed is True
    table.update.assert_called_once()
    payload = table.update.call_args[0][0]
    assert payload["user_id"] == "new-uid"
    assert payload["staff_email"] == "info@example.ru"
    table.eq.assert_called_once_with("user_id", "old-uid")


def test_sync_staff_role_auth_user_id_noop_when_same() -> None:
    with patch(
        "sfrfr.db.staff_roles._staff_row_by_email",
        return_value={"user_id": "same-uid", "role": "admin"},
    ):
        changed = sync_staff_role_auth_user_id(
            email="info@example.ru",
            auth_user_id="same-uid",
        )
    assert changed is False
