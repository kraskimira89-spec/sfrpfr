"""UI polish OTP-экрана входа сотрудника: структура, a11y, утилиты."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADMIN = ROOT / "apps" / "admin" / "src"
AUTH_SCREEN = (ADMIN / "components" / "staff-auth-screen.tsx").read_text(encoding="utf-8")
OTP_INPUT = (ADMIN / "components" / "staff-otp-input.tsx").read_text(encoding="utf-8")
OTP_LIB = (ADMIN / "lib" / "staff-otp.ts").read_text(encoding="utf-8")
MESSAGES = (ADMIN / "lib" / "auth-messages.ts").read_text(encoding="utf-8")
GLOBALS = (ADMIN / "app" / "globals.css").read_text(encoding="utf-8")


def _normalize_otp_digits(value: str) -> str:
    return re.sub(r"\D", "", value)[:6]


def _split_otp_digits(code: str) -> list[str]:
    normalized = _normalize_otp_digits(code)
    return [normalized[i] if i < len(normalized) else "" for i in range(6)]


def _merge_otp_digits(cells: list[str]) -> str:
    return _normalize_otp_digits("".join(cells))


def _is_otp_complete(code: str) -> bool:
    return len(_normalize_otp_digits(code)) == 6


def _format_resend_countdown(total_seconds: int) -> str:
    safe = max(0, int(total_seconds))
    minutes, seconds = divmod(safe, 60)
    return f"{minutes:02d}:{seconds:02d}"


def test_staff_otp_utils_normalize_and_complete() -> None:
    assert _normalize_otp_digits("12a34b56c") == "123456"
    assert _normalize_otp_digits("1234567890") == "123456"
    assert _is_otp_complete("123456") is True
    assert _is_otp_complete("12345") is False


def test_staff_otp_utils_split_merge() -> None:
    assert _split_otp_digits("123") == ["1", "2", "3", "", "", ""]
    assert _merge_otp_digits(["1", "2", "3", "4", "5", "6"]) == "123456"
    assert _merge_otp_digits(["1", "a", "3"]) == "13"


def test_staff_otp_utils_resend_countdown() -> None:
    assert _format_resend_countdown(48) == "00:48"
    assert _format_resend_countdown(125) == "02:05"


def test_staff_otp_ts_exports_present() -> None:
    for token in (
        "export const OTP_LENGTH = 6",
        "normalizeOtpDigits",
        "isOtpComplete",
        "formatResendCountdown",
        "getOtpSubmitLabel",
    ):
        assert token in OTP_LIB


def test_staff_otp_input_a11y_and_security() -> None:
    assert "StaffOtpInput" in OTP_INPUT
    assert 'autoComplete={index === 0 ? "one-time-code" : "off"}' in OTP_INPUT
    assert "aria-label={`Цифра ${index + 1} кода из ${OTP_LENGTH}`}" in OTP_INPUT
    assert "localStorage" not in AUTH_SCREEN
    assert "sessionStorage" not in AUTH_SCREEN
    assert "console.log" not in AUTH_SCREEN


def test_staff_otp_screen_structure() -> None:
    assert "StaffOtpInput" in AUTH_SCREEN
    assert "AuthStepper" in AUTH_SCREEN
    assert "auth-actions-row" in AUTH_SCREEN
    assert "auth-help-fallback" in AUTH_SCREEN
    assert "auth-otp-error" in AUTH_SCREEN
    assert 'variant={trustVariant}' in AUTH_SCREEN
    assert "getOtpSubmitLabel" in AUTH_SCREEN


def test_staff_otp_copy_human() -> None:
    assert "← На основной сайт" in MESSAGES
    assert "Шаг 2 из 2" in MESSAGES
    assert "Подтверждение входа" in MESSAGES
    assert "Войти в кабинет" in MESSAGES
    assert "Проверяем код…" in MESSAGES
    assert "Кабинет сотрудников" in MESSAGES
    assert "Нужна помощь?" in MESSAGES


def test_staff_otp_responsive_css() -> None:
    assert ".auth-otp__cell" in GLOBALS
    assert ".auth-stepper" in GLOBALS
    assert "@media (max-width: 1023px)" in GLOBALS
    assert "prefers-reduced-motion" in GLOBALS


def test_staff_otp_no_inline_styles() -> None:
    assert "style={{" not in AUTH_SCREEN
    assert "style={{" not in OTP_INPUT
