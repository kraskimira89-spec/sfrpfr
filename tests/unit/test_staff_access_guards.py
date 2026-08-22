"""Guards P0: self-change, last admin, confirm admin grant."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from sfrfr.db import staff_access


def test_self_change_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    audits: list[dict] = []

    def fake_audit(**kwargs):  # noqa: ANN003
        audits.append(kwargs)

    monkeypatch.setattr(staff_access, "count_active_admins", lambda **_: 2)
    monkeypatch.setattr(staff_access, "write_staff_audit", fake_audit)
    with pytest.raises(HTTPException) as exc:
        staff_access.validate_staff_change(
            actor_id="u1",
            target_user_id="u1",
            old_role="operator",
            new_role="admin",
            old_status="active",
            new_status="active",
            confirm_admin_grant=True,
        )
    assert exc.value.status_code == 403
    assert audits and audits[0]["event"] == "staff_self_change"
    assert audits[0]["result"] == "denied"


def test_last_admin_demotion_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    def fake_audit(**kwargs):  # noqa: ANN003
        calls.append(kwargs)

    monkeypatch.setattr(staff_access, "count_active_admins", lambda **_: 0)
    monkeypatch.setattr(staff_access, "write_staff_audit", fake_audit)
    with pytest.raises(HTTPException) as exc:
        staff_access.validate_staff_change(
            actor_id="boss",
            target_user_id="only-admin",
            old_role="admin",
            new_role="operator",
            old_status="active",
            new_status="active",
            confirm_admin_grant=False,
        )
    assert exc.value.status_code == 403
    assert calls and calls[0]["result"] == "denied"
    assert calls[0]["event"] == "staff_last_admin"


def test_admin_grant_requires_confirm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(staff_access, "count_active_admins", lambda **_: 2)
    with pytest.raises(HTTPException) as exc:
        staff_access.validate_staff_change(
            actor_id="boss",
            target_user_id="u2",
            old_role="operator",
            new_role="admin",
            old_status="active",
            new_status="active",
            confirm_admin_grant=False,
        )
    assert exc.value.status_code == 400
    assert "confirm_admin_grant" in str(exc.value.detail)


def test_admin_grant_ok_with_confirm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(staff_access, "count_active_admins", lambda **_: 2)
    staff_access.validate_staff_change(
        actor_id="boss",
        target_user_id="u2",
        old_role="operator",
        new_role="admin",
        old_status="active",
        new_status="active",
        confirm_admin_grant=True,
    )


def test_serialize_member_hides_invite_hash() -> None:
    member = staff_access.serialize_member(
        {
            "user_id": "11111111-1111-1111-1111-111111111111",
            "staff_email": "a@example.com",
            "display_name": "Анна",
            "role": "expert",
            "status": "invited",
            "invite_token_hash": "secret",
            "last_sign_in_at": None,
        }
    )
    assert member["email"] == "a@example.com"
    assert member["display_name"] == "Анна"
    assert "invite_token_hash" not in member
    assert member["user_id"].startswith("1111")
