"""Вход через MAX для пользователей уже в системе — без кода на сайте."""

from __future__ import annotations

from sfrfr.integrations.max.handler import _send_confirm_web_login
from sfrfr.security import login_pending


class _FakeBot:
    available = True

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send_message(self, **kwargs):  # noqa: ANN003
        self.sent.append(kwargs)
        return {"ok": True}


def _clear_pending() -> None:
    login_pending._BY_TICKET.clear()  # noqa: SLF001
    login_pending._BY_CODE.clear()  # noqa: SLF001
    login_pending._BY_MAX.clear()  # noqa: SLF001
    login_pending._BY_OTP_CODE.clear()  # noqa: SLF001


def test_send_confirm_web_login_approves_returning_client(monkeypatch) -> None:
    """Клиент в системе: кнопка в MAX → approved, без code_sent."""
    _clear_pending()
    site_pending = login_pending.create_pending()

    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._ensure_client_row",
        lambda _uid: {
            "id": "c1",
            "user_id": "u1",
            "email": "max_888@clients.sfrfr.local",
            "max_user_id": "888",
        },
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._auth_email_for_row",
        lambda _row, uid: f"max_{uid}@clients.sfrfr.local",
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._token_hash_for_max",
        lambda _uid: ("max_888@clients.sfrfr.local", "hash-returning"),
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._reply",
        lambda bot, **kwargs: bot.send_message(**kwargs),
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._send_open_cabinet_link",
        lambda *args, **kwargs: None,
    )

    bot = _FakeBot()
    result = _send_confirm_web_login(bot, user_id="888", chat_id=1)
    assert result.ok is True
    assert result.action == "login_approved"

    pending = login_pending.get_pending(site_pending.ticket_id)
    assert pending is not None
    assert pending.status == "approved"
    assert pending.token_hash == "hash-returning"
    assert pending.status != "code_sent"
