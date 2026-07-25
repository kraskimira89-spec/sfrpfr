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


def test_unified_login_terms() -> None:
    from sfrfr.security.login_otp import (
        CONFIRM_WEB_LOGIN_LABEL,
        GET_CODE_IN_BROWSER_LABEL,
        SHOW_CODE_BUTTON_LABEL,
        after_start_login_hint,
        get_code_in_browser_url,
    )

    assert GET_CODE_IN_BROWSER_LABEL == "Получить код в браузере"
    assert SHOW_CODE_BUTTON_LABEL == "Показать код здесь"
    assert CONFIRM_WEB_LOGIN_LABEL == "Подтвердить вход в браузере"
    hint = after_start_login_hint()
    assert GET_CODE_IN_BROWSER_LABEL in hint
    assert "Показать код для MAX" not in hint
    assert "Получить подтверждение" not in hint
    assert "код" in hint.lower()
    url = get_code_in_browser_url(mode="login")
    assert "mode=login" in url
    assert "channel=max" in url
    assert "get_code=1" in url


def test_channel_choice_after_login() -> None:
    from sfrfr.integrations.max.client import inline_channel_choice_keyboard
    from sfrfr.security.login_otp import (
        WORK_IN_APP_LABEL,
        WORK_IN_INTERFACE_LABEL,
        channel_choice_after_login_message,
    )

    text = channel_choice_after_login_message()
    assert "Вход выполнен" in text
    kb = inline_channel_choice_keyboard(
        app_url="https://example.com/app/",
        cabinet_url="https://example.com/cabinet/?auth=max&t=1",
    )
    buttons = kb[0]["payload"]["buttons"]
    labels = {btn[0]["text"] for btn in buttons}
    assert labels == {WORK_IN_APP_LABEL, WORK_IN_INTERFACE_LABEL}
    text = confirm_web_login_message(code="123456")
    assert "123456" in text
    assert "кнопк" in text.lower()


def test_confirm_message_is_short_action() -> None:
    text = confirm_web_login_message()
    assert "Нажмите кнопку" in text
    assert "кабинет" in text.lower()
    assert len(text) < 80