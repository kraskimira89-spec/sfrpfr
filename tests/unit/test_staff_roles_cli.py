"""Тесты staff-grant helpers."""

from __future__ import annotations

import pytest

from sfrfr.security.auth import StaffRole


def test_staff_role_values() -> None:
    assert StaffRole("admin") is StaffRole.ADMIN
    assert StaffRole("expert") is StaffRole.EXPERT
    with pytest.raises(ValueError):
        StaffRole("superuser")
