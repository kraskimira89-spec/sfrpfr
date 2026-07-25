"""Unit-тесты OTP и login-link через MAX."""

from urllib.parse import parse_qs, urlparse

from sfrfr.security.login_otp import (
    confirm_web_login_message,
    issue_login_link,
    issue_login_otp,
    normalize_phone,
    verify_login_link,
    verify_login_otp,
)


def test_normalize_phone_ru() -> None:
    assert normalize_phone("+7 (909) 195-04-08") == "+79091950408"
    assert normalize_phone("89091950408") == "+79091950408"
    assert normalize_phone("79091950408") == "+79091950408"


def test_issue_and_verify_login_otp() -> None:
    issued = issue_login_otp(contact="max_1@clients.sfrfr.local", max_user_id="12345")
    assert len(issued.code) == 6
    assert "|" in issued.ticket
    assert issued.ticket.count(".") >= 2
    ok = verify_login_otp(ticket=issued.ticket, code=issued.code)
    assert ok == ("max_1@clients.sfrfr.local", "12345")


def test_verify_rejects_bad_code() -> None:
    issued = issue_login_otp(contact="a@b.c", max_user_id="9")
    assert verify_login_otp(ticket=issued.ticket, code="000000") is None


def test_issue_and_verify_login_link() -> None:
    issued = issue_login_link(contact="max_1@clients.sfrfr.local", max_user_id="12345")
    assert len(issued.code) == 6
    assert issued.login_url.startswith("https://")
    parsed = urlparse(issued.login_url)
    qs = parse_qs(parsed.query)
    assert qs.get("auth") == ["max"]
    assert "t" in qs
    ok = verify_login_link(link_token=issued.link_token)
    assert ok == ("max_1@clients.sfrfr.local", "12345")
    assert verify_login_link(link_token="bad") is None


def test_confirm_web_login_copy() -> None:
    text = confirm_web_login_message(code="123456")
    assert "123456" in text
    assert "кнопк" in text.lower()


def test_confirm_message_is_short_action() -> None:
    text = confirm_web_login_message()
    assert "Нажмите кнопку" in text
    assert len(text) < 40