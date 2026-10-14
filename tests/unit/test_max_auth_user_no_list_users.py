"""MAX auth ensure не ходит в list_users (ложный timeout ensure_case)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfrfr.db.client_channels import ClientChannelRepository


def test_ensure_auth_user_for_max_skips_list_users() -> None:
    client = MagicMock()
    created = MagicMock()
    created.user = MagicMock(id="auth-uid-1")
    client.auth.admin.create_user.return_value = created
    client.auth.admin.list_users = MagicMock()

    repo = ClientChannelRepository.__new__(ClientChannelRepository)
    repo.client = client

    with patch("sfrfr.db.staff_roles.find_user_by_email") as find_email:
        uid = repo._ensure_auth_user_for_max("123", "max_123@clients.sfrfr.local")

    assert uid == "auth-uid-1"
    find_email.assert_not_called()
    client.auth.admin.list_users.assert_not_called()
    client.auth.admin.create_user.assert_called_once()
