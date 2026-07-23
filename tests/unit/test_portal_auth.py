"""Тесты JWT/RBAC helpers для portal API."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from sfrfr.security.auth import Principal, StaffRole, require_admin, require_staff


def test_require_staff_rejects_client() -> None:
    principal = Principal(user_id="u1", email="c@example.com", role=None)
    with pytest.raises(HTTPException) as exc:
        require_staff(principal)
    assert exc.value.status_code == 403


def test_require_admin_allows_admin() -> None:
    principal = Principal(user_id="u2", email="a@example.com", role=StaffRole.ADMIN)
    assert require_admin(principal) is principal


def test_require_admin_rejects_operator() -> None:
    principal = Principal(user_id="u3", email="o@example.com", role=StaffRole.OPERATOR)
    with pytest.raises(HTTPException) as exc:
        require_admin(principal)
    assert exc.value.status_code == 403
