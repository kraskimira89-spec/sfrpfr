"""ТЗ-25: ops-бот MAX."""

from __future__ import annotations

from pathlib import Path

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
    assert "Проверка стажа-Ops" in bot.sent[0]["text"]
    assert "admin.example" in bot.sent[0]["text"]
    assert bot.sent[0].get("attachments")
    get_settings.cache_clear()


def test_ops_login_shows_pair_hint(monkeypatch) -> None:
    from sfrfr.security.login_pending import create_pending

    monkeypatch.setenv("ADMIN_PUBLIC_URL", "https://admin.example")
    monkeypatch.setenv("MAX_OPS_LLM_ENABLED", "0")
    get_settings.cache_clear()
    pending = create_pending(audience="staff", staff_email="op@example.com")
    bot = _SilentBot()
    result = handle_ops_update(_msg(42, "/login"), bot=bot)
    assert result.action in {
        "ops_staff_pair_hint",
        "login_pending_manager",
        "login_approved_trusted",
    }
    assert bot.sent
    texts = " ".join(str(m.get("text") or "") for m in bot.sent)
    assert pending.pair_code in texts or "6 цифр" in texts or "Готово" in texts
    get_settings.cache_clear()


def test_ops_redirects_unknown_message(monkeypatch) -> None:
    monkeypatch.setenv("MAX_CHAT_URL", "https://max.ru/client_bot")
    monkeypatch.setenv("MAX_OPS_LLM_ENABLED", "0")
    get_settings.cache_clear()
    bot = _SilentBot()
    result = handle_ops_update(_msg(42, "случайный текст без смысла для бота"), bot=bot)
    assert result.action == "ops_redirect_client"
    assert "Стаж и пенсия" in bot.sent[0]["text"]
    assert "служебный" in bot.sent[0]["text"].lower()
    get_settings.cache_clear()


def test_ops_llm_answers_dm_question(monkeypatch) -> None:
    monkeypatch.setenv("MAX_OPS_LLM_ENABLED", "1")
    get_settings.cache_clear()
    bot = _SilentBot()
    monkeypatch.setattr(
        "sfrfr.integrations.max.ops_llm.answer_specialist_question",
        lambda q, **_: f"AI:{q}",
    )
    result = handle_ops_update(_msg(42, "Как отвечать клиенту про подачу?"), bot=bot)
    assert result.action == "ops_llm_answer"
    assert bot.sent[0]["text"].startswith("AI:")
    get_settings.cache_clear()


def test_ops_channel_ignores_without_mention(monkeypatch) -> None:
    monkeypatch.setenv("MAX_OPS_LLM_ENABLED", "1")
    monkeypatch.setenv("MAX_SPECIALISTS_CHANNEL_CHAT_ID", "-77768587291288")
    get_settings.cache_clear()
    bot = _SilentBot()
    update = {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": 7},
            "body": {"text": "просто обсуждение без бота"},
            "recipient": {"chat_id": -77768587291288},
        },
    }
    result = handle_ops_update(update, bot=bot)
    assert result.action == "ops_channel_ignore"
    assert not bot.sent
    get_settings.cache_clear()


def test_ops_channel_ask_triggers_llm(monkeypatch) -> None:
    monkeypatch.setenv("MAX_OPS_LLM_ENABLED", "1")
    monkeypatch.setenv("MAX_SPECIALISTS_CHANNEL_CHAT_ID", "-77768587291288")
    get_settings.cache_clear()
    bot = _SilentBot()
    monkeypatch.setattr(
        "sfrfr.integrations.max.ops_llm.answer_specialist_question",
        lambda q, **_: f"ASK:{q}",
    )
    update = {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": 7},
            "body": {"text": "/ask Какие документы нужны без ИЛС?"},
            "recipient": {"chat_id": -77768587291288},
        },
    }
    result = handle_ops_update(update, bot=bot)
    assert result.action == "ops_llm_answer"
    assert "ASK:" in bot.sent[0]["text"]
    get_settings.cache_clear()


def test_ops_bot_added_remembers(monkeypatch) -> None:
    store = Path("var") / "test_max_ops_channel_ids.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    if store.exists():
        store.unlink()
    monkeypatch.setattr(
        "sfrfr.integrations.max.channel_ids.store_path",
        lambda: store,
    )
    get_settings.cache_clear()
    bot = _SilentBot()
    update = {
        "update_type": "bot_added",
        "chat_id": -77768587291288,
        "user": {"user_id": 1},
    }
    result = handle_ops_update(update, bot=bot)
    assert result.ok
    assert result.action == "bot_added"
    assert "77768587291288" in (result.detail or "")
    assert not bot.sent
    store.unlink(missing_ok=True)
    get_settings.cache_clear()


def test_lead_notify_sends_to_specialists_channel(monkeypatch) -> None:
    from sfrfr.api.routes.public_leads import _notify_max_managers_new_lead

    sent: list[dict] = []

    class _Bot:
        available = True

        def send_message(self, **kwargs):  # noqa: ANN003
            sent.append(kwargs)
            return {"ok": True}

    monkeypatch.setenv("MAX_OPS_BOT_TOKEN", "ops-token")
    monkeypatch.setenv("STAFF_LOGIN_APPROVER_MAX_USER_IDS", "")
    monkeypatch.setenv("STAFF_LOGIN_APPROVER_MAX_CHAT_IDS", "")
    monkeypatch.setenv("MAX_SPECIALISTS_CHANNEL_CHAT_ID", "-77768587291288")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "sfrfr.integrations.max.ops_bot.get_ops_bot",
        lambda: _Bot(),
    )
    monkeypatch.setattr(
        "sfrfr.db.staff_roles.list_manager_max_user_ids",
        lambda extra_ids="": [],
    )
    result = _notify_max_managers_new_lead(
        case_id="case-1",
        full_name="Тест",
        contact="+7900",
        channel="site",
        crm_url=None,
    )
    assert result["ok"] is True
    assert result["team_channel_sent"] is True
    assert sent and str(sent[0]["chat_id"]) == "-77768587291288"
    get_settings.cache_clear()
