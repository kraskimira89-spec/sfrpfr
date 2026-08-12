"""ТЗ-25: ops-бот MAX."""

from __future__ import annotations

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.client import MaxBotClient
from sfrfr.integrations.max.ops_bot import get_ops_bot, handle_ops_update


class _SilentBot(MaxBotClient):
    def __init__(self) -> None:
        super().__init__(token="test-ops-token")
        self.sent: list[dict] = []

    def send_message(self, **kwargs):  # noqa: ANN003
        self.sent.append(kwargs)
        return {"ok": True}


def _msg(user_id: int, text: str) -> dict:
    return {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": user_id},
            "body": {"text": text},
            "recipient": {"chat_id": user_id},
        },
    }


def test_get_ops_bot_falls_back_to_client_token(monkeypatch) -> None:
    monkeypatch.setenv("MAX_BOT_TOKEN", "client-token")
    monkeypatch.setenv("MAX_OPS_BOT_TOKEN", "")
    get_settings.cache_clear()
    bot = get_ops_bot()
    assert bot.token == "client-token"
    assert bot.uses_ops_token is False
    get_settings.cache_clear()


def test_get_ops_bot_uses_ops_token(monkeypatch) -> None:
    monkeypatch.setenv("MAX_BOT_TOKEN", "client-token")
    monkeypatch.setenv("MAX_OPS_BOT_TOKEN", "ops-token")
    get_settings.cache_clear()
    bot = get_ops_bot()
    assert bot.token == "ops-token"
    assert bot.uses_ops_token is True
    get_settings.cache_clear()


def test_ops_start_welcome(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_PUBLIC_URL", "https://admin.example")
    monkeypatch.setenv("MAX_CHAT_URL", "https://max.ru/client_bot")
    get_settings.cache_clear()
    bot = _SilentBot()
    result = handle_ops_update(_msg(42, "/start"), bot=bot)
    assert result.ok
    assert result.action == "ops_start"
    assert bot.sent
    assert "Служебный бот" in bot.sent[0]["text"]
    assert "admin.example" in bot.sent[0]["text"]
    get_settings.cache_clear()


def test_ops_redirects_client_commands(monkeypatch) -> None:
    monkeypatch.setenv("MAX_CHAT_URL", "https://max.ru/client_bot")
    get_settings.cache_clear()
    bot = _SilentBot()
    result = handle_ops_update(_msg(42, "/login"), bot=bot)
    assert result.action == "ops_redirect_client"
    assert "Стаж и пенсия" in bot.sent[0]["text"]
    assert "служебный" in bot.sent[0]["text"].lower()
    get_settings.cache_clear()
