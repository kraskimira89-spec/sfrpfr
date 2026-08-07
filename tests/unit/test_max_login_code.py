"""Бот MAX: /login выдаёт код для ввода на сайте."""

from __future__ import annotations

from sfrfr.integrations.max.handler import _issue_login_code_to_max
from sfrfr.security import login_pending
from sfrfr.security.login_otp import verify_login_otp


class _FakeBot:
    available = True

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send_message(self, **kwargs):  # noqa: ANN003
        self.sent.append(kwargs)
        return {"ok": True}


def test_issue_login_code_to_max_sends_code(monkeypatch) -> None:
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-for-otp")
    login_pending._BY_TICKET.clear()  # noqa: SLF001
    login_pending._BY_CODE.clear()  # noqa: SLF001
    login_pending._BY_MAX.clear()  # noqa: SLF001
    login_pending._BY_OTP_CODE.clear()  # noqa: SLF001

    site = login_pending.create_pending()
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._ensure_client_row",
        lambda _uid: {
            "id": "c1",
            "user_id": None,
            "email": "max_555@clients.sfrfr.local",
            "max_user_id": "555",
        },
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._auth_email_for_row",
        lambda _row, uid: f"max_{uid}@clients.sfrfr.local",
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._reply",
        lambda bot, **kwargs: bot.send_message(**kwargs),
    )

    bot = _FakeBot()
    result = _issue_login_code_to_max(bot, user_id="555", chat_id=1)
    assert result.ok is True
    assert result.action == "login_code_sent"
    assert bot.sent
    text = bot.sent[0]["text"]
    assert "Код для входа:" in text
    assert "verify_ticket=" in text
    assert "10 минут" in text

    pending = login_pending.get_pending(site.ticket_id)
    assert pending is not None
    assert pending.status == "code_sent"
    assert pending.otp_verify_ticket

    # Из ответа достаём 6 цифр кода
    import re

    match = re.search(r"Код для входа:\s*(\d{6})", text)
    assert match
    code = match.group(1)
    assert verify_login_otp(ticket=pending.otp_verify_ticket, code=code) is not None
    assert login_pending.lookup_otp_verify_ticket_by_code(code) == pending.otp_verify_ticket
