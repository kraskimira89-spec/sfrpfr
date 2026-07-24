"""Unit-тесты OTP входа через MAX (HMAC ticket)."""

from sfrfr.security.login_otp import issue_login_otp, normalize_phone, verify_login_otp


def test_normalize_phone_ru() -> None:
    assert normalize_phone("+7 (909) 195-04-08") == "+79091950408"
    assert normalize_phone("89091950408") == "+79091950408"
    assert normalize_phone("79091950408") == "+79091950408"


def test_issue_and_verify_login_otp() -> None:
    issued = issue_login_otp(contact="max_1@clients.sfrfr.local", max_user_id="12345")
    assert len(issued.code) == 6
    assert issued.ticket
    ok = verify_login_otp(ticket=issued.ticket, code=issued.code)
    assert ok == ("max_1@clients.sfrfr.local", "12345")


def test_verify_rejects_bad_code() -> None:
    issued = issue_login_otp(contact="a@b.c", max_user_id="9")
    assert verify_login_otp(ticket=issued.ticket, code="000000") is None
