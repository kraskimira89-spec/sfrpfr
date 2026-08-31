"""Auth Send Email Hook: magic link + OTP в письме."""

from __future__ import annotations

from sfrfr.api.routes.supabase_auth_email import (
    _compose,
    confirm_url_from_email_data,
)


def test_confirm_url_from_email_data() -> None:
    url = confirm_url_from_email_data(
        {
            "site_url": "https://frualvycousvvyjivybu.supabase.co",
            "token_hash": "abc123",
            "email_action_type": "signup",
            "redirect_to": "https://cabinet.proverkastaza.ru/",
        }
    )
    assert url.startswith("https://frualvycousvvyjivybu.supabase.co/auth/v1/verify?")
    assert "token=abc123" in url
    assert "type=signup" in url
    assert "redirect_to=" in url


def test_confirm_url_empty_without_hash() -> None:
    assert confirm_url_from_email_data({"site_url": "https://x.supabase.co"}) == ""


def test_compose_includes_magic_link_and_token() -> None:
    confirm = (
        "https://x.supabase.co/auth/v1/verify?token=h&type=signup"
        "&redirect_to=https%3A%2F%2Fcabinet.proverkastaza.ru%2F"
    )
    subject, plain, html = _compose(
        "signup",
        "123456",
        "Здравствуйте!",
        confirm_url=confirm,
    )
    assert "Вход в кабинет" in subject
    assert confirm in plain
    assert "123456" in plain
    assert "Войти в кабинет" in html
    assert "token=h" in html
    assert "123456" in html


def test_compose_token_only_fallback() -> None:
    _subject, plain, html = _compose("magiclink", "654321", "Здравствуйте!")
    assert "654321" in plain
    assert "654321" in html
    assert 'href="' not in html or "Войти в кабинет" not in html
