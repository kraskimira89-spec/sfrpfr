"""P2.1: клиентский вход без технического жаргона и без enumeration."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CABINET = ROOT / "apps" / "cabinet" / "src"
MESSAGES = (CABINET / "lib" / "auth-messages.ts").read_text(encoding="utf-8")
UI = (CABINET / "components" / "client-cabinet.tsx").read_text(encoding="utf-8")


def test_client_ui_hides_supabase_config_error() -> None:
    assert "нет public ключа" not in UI
    assert "нет public ключа" not in MESSAGES
    assert "public ключа Supabase" not in UI
    assert 'setNotice("Кабинет ещё не настроен' not in UI


def test_auth_messages_are_human() -> None:
    assert "Вход временно недоступен" in MESSAGES
    assert "Код не подошёл" in MESSAGES
    assert "Срок действия кода закончился" in MESSAGES
    assert "name@example.ru" in MESSAGES
    assert "Если этот адрес можно использовать для входа" in MESSAGES


def test_unified_login_copy_in_cabinet() -> None:
    assert "Войти в личный кабинет" in MESSAGES
    assert "LOGIN_COPY.title" in UI
    assert 'role="tablist"' not in UI
    assert "auth-tabs" not in UI
    assert "Вернуться на сайт" in UI
    assert "auth-return-panel" not in UI
    assert "shouldCreateUser: true" in UI
    assert "Аккаунт не найден" not in UI
    assert "NEXT_PUBLIC_SUPABASE_ANON_KEY" in UI


def test_generic_otp_response_not_enumerating() -> None:
    assert "otpSentGeneric" in UI
    assert "signups not allowed" in UI
    assert "setOtpSent(true)" in UI
