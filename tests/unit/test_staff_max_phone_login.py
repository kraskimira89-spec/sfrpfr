"""Staff MAX login: телефон → trusted_max / ops-confirm (не email)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sfrfr.db.staff_roles import get_staff_email_by_phone
from sfrfr.security.login_otp import normalize_phone

ROOT = Path(__file__).resolve().parents[2]
ADMIN = ROOT / "apps" / "admin" / "src"
MESSAGES = (ADMIN / "lib" / "auth-messages.ts").read_text(encoding="utf-8")
AUTH_SCREEN = (ADMIN / "components" / "staff-auth-screen.tsx").read_text(encoding="utf-8")
CSS = (ADMIN / "app" / "globals.css").read_text(encoding="utf-8")
PORTAL = (ROOT / "src" / "sfrfr" / "api" / "routes" / "portal.py").read_text(encoding="utf-8")


def test_normalize_owner_phone() -> None:
    assert normalize_phone("+7 (909) 195-04-08") == "+79091950408"
    assert normalize_phone("89091950408") == "+79091950408"


def test_get_staff_email_by_phone_from_staff_phone_column() -> None:
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    table.execute.return_value = MagicMock(
        data=[
            {
                "user_id": "uid-1",
                "role": "admin",
                "staff_email": "info@example.ru",
                "staff_phone": "+79091950408",
                "trusted_login_max_user_id": "6407832",
            }
        ]
    )
    client = MagicMock()
    client.table.return_value = table

    with patch("sfrfr.db.staff_roles.get_supabase_client", return_value=client):
        email = get_staff_email_by_phone("+7 909 195-04-08")

    assert email == "info@example.ru"
    client.table.assert_called_with("staff_roles")


def test_get_staff_email_by_phone_default_specialist_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_DEFAULT_SPECIALIST_PHONE", "+79091950408")
    monkeypatch.setenv("MAX_DEFAULT_SPECIALIST_MAX_USER_ID", "6407832")

    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    # first query by staff_phone → empty; second by trusted/max → hit
    table.execute.side_effect = [
        MagicMock(data=[]),
        MagicMock(
            data=[
                {
                    "user_id": "uid-1",
                    "role": "admin",
                    "staff_email": "info@example.ru",
                    "trusted_login_max_user_id": "6407832",
                    "max_user_id": "6407832",
                }
            ]
        ),
    ]
    client = MagicMock()
    client.table.return_value = table

    with patch("sfrfr.db.staff_roles.get_supabase_client", return_value=client):
        from sfrfr.core.config import get_settings

        get_settings.cache_clear()
        try:
            email = get_staff_email_by_phone("89091950408")
        finally:
            get_settings.cache_clear()

    assert email == "info@example.ru"


def test_staff_ui_max_login_uses_phone_not_email() -> None:
    assert 'id="staff-phone"' in AUTH_SCREEN
    max_fn = AUTH_SCREEN.split("async function requestMaxLogin")[1].split("async function")[0]
    assert "audience: \"staff\"" in max_fn or "audience: 'staff'" in max_fn
    assert "phone:" in max_fn or "phone :" in max_fn
    assert "email:" not in max_fn.replace("emailRequired", "")
    assert "phoneRequired" in MESSAGES
    assert "phoneLabel" in MESSAGES


def test_staff_max_api_accepts_phone() -> None:
    assert "get_staff_email_by_phone" in PORTAL or "staff_phone" in PORTAL
    assert 'reason="missing_phone"' in PORTAL or "missing_phone" in PORTAL


def test_auth_alt_btn_hover_keeps_readable_text() -> None:
    block_start = CSS.find(".auth-alt-btn:hover")
    assert block_start >= 0
    block = CSS[block_start : block_start + 220]
    assert "color:" in block
    assert "background:" in block
    assert "var(--ink)" in block or "#142033" in block or "#fff" in block
