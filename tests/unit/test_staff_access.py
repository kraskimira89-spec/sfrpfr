"""Безопасные операции staff_roles: сериализация и защита последнего admin."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from sfrfr.db.staff_access import serialize_member, validate_staff_change


def test_serialize_member_defaults_status_and_email() -> None:
    row = serialize_member(
        {"user_id": "00000000-0000-0000-0000-000000000001", "role": "admin", "email": "ops@x.ru"}
    )
    assert row["status"] == "active"
    assert row["role"] == "admin"
    assert row["email"] == "ops@x.ru"


def test_validate_blocks_self_role_change(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sfrfr.db.staff_access.write_staff_audit", lambda **_kwargs: None)
    with pytest.raises(HTTPException) as exc:
        validate_staff_change(
            actor_id="u1",
            target_user_id="u1",
            old_role="admin",
            new_role="expert",
            old_status="active",
            new_status="active",
            confirm_admin_grant=False,
        )
    assert exc.value.status_code == 403
