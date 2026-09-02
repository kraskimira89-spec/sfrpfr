"""P2.2: вход сотрудника без технического жаргона и без enumeration."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADMIN = ROOT / "apps" / "admin" / "src"
MESSAGES = (ADMIN / "lib" / "auth-messages.ts").read_text(encoding="utf-8")
UI = (ADMIN / "components" / "admin-cabinet.tsx").read_text(encoding="utf-8")
AUTH_SCREEN = (ADMIN / "components" / "staff-auth-screen.tsx").read_text(encoding="utf-8")
PORTAL = (ROOT / "src" / "sfrfr" / "api" / "routes" / "portal.py").read_text(encoding="utf-8")


def test_staff_ui_no_technical_auth_leaks() -> None:
    combined = UI + AUTH_SCREEN
    banned = (
        "staff_roles",
        "staff-grant",
        "нет public ключа",
        "public ключа Supabase",
        "Email не найден",
        "auth-return-panel",
        "auth-tabs",
        "max-login-steps",
    )
    for phrase in banned:
        assert phrase not in combined, f"запрещено «{phrase}»"


def test_staff_login_copy_human() -> None:
    assert "Вход в кабинет сотрудника" in MESSAGES
    assert "Если этот адрес можно использовать для входа" in MESSAGES
    assert "Безопасный вход" in MESSAGES
    assert "Доступ пока не подтверждён" in MESSAGES


def test_staff_auth_screen_uses_trust_panel() -> None:
    assert "StaffAuthTrustPanel" in AUTH_SCREEN
    assert "StaffAuthScreen" in UI
    assert "StaffAccessGate" in UI


def test_staff_max_otp_no_enumeration_in_api() -> None:
    assert "Email не найден в staff" not in PORTAL
    assert "staff_email_unknown" in PORTAL
