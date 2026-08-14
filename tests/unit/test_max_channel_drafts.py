"""Премодерация постов клиентского канала MAX."""

from __future__ import annotations

import uuid
from pathlib import Path

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.channel_drafts import (
    ChannelDraftStore,
    edit_payload,
    format_review_message,
    get_draft_store,
    parse_draft_callback,
    publish_payload,
    reset_draft_store,
    review_keyboard,
)
from sfrfr.integrations.max.client import MaxBotClient
from sfrfr.integrations.max.ops_bot import handle_ops_update

_TEST_ROOT = Path("var/test-tmp/max-channel-drafts")


def _draft_path() -> Path:
    _TEST_ROOT.mkdir(parents=True, exist_ok=True)
    return _TEST_ROOT / f"drafts-{uuid.uuid4().hex}.json"


class _SilentOps(MaxBotClient):
    def __init__(self) -> None:
        super().__init__(token="test-ops-token")
        self.sent: list[dict] = []
        self.answers: list[dict] = []

    def send_message(self, **kwargs):  # noqa: ANN003
        self.sent.append(kwargs)
        return {"ok": True, "message": {"url": "https://max.ru/x", "body": {"mid": "m1"}}}

    def answer_callback(self, callback_id: str, **kwargs):  # noqa: ANN003
        self.answers.append({"callback_id": callback_id, **kwargs})
        return {"ok": True}


def test_parse_and_keyboard() -> None:
    store = ChannelDraftStore(_draft_path())
    draft = store.create(text="Текст поста", source_id="07-no-calc", draft_id="abc123")
    assert publish_payload(draft.id) == "chdraft:pub:abc123"
    assert edit_payload(draft.id) == "chdraft:edit:abc123"
    assert parse_draft_callback("chdraft:pub:abc123") == ("pub", "abc123")
    kb = review_keyboard(draft)
    buttons = kb[0]["payload"]["buttons"]
    assert buttons[0][0]["text"] == "Опубликовать"
    assert buttons[1][0]["type"] == "clipboard"
    assert buttons[2][0]["text"] == "Прислать правку"
    assert "ops-бот" in format_review_message(draft)


def test_edit_wait_replies_in_ops_dm(monkeypatch) -> None:
    path = _draft_path()
    reset_draft_store(path)
    get_draft_store(path).create(text="Старый текст", draft_id="ed1")
    get_draft_store().mark_waiting_edit("ed1", "42")

    monkeypatch.setenv("MAX_OPS_LLM_ENABLED", "0")
    monkeypatch.setenv("MAX_SPECIALISTS_CHANNEL_CHAT_ID", "-77768587291288")
    get_settings.cache_clear()
    bot = _SilentOps()
    # личка: chat_id != канал команды
    update = {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": 42},
            "body": {"text": "Новый текст поста для канала клиентов, достаточно длинный."},
            "recipient": {"chat_id": 42},
        },
    }
    result = handle_ops_update(update, bot=bot)
    assert result.action == "chdraft_updated"
    assert get_draft_store().get("ed1").text.startswith("Новый текст")
    last = bot.sent[-1]
    assert last.get("user_id") == "42"
    assert last.get("chat_id") is None
    assert "Опубликовать" in str(last.get("attachments"))
    get_settings.cache_clear()


def test_long_paste_in_ops_dm_creates_draft(monkeypatch) -> None:
    path = _draft_path()
    reset_draft_store(path)
    monkeypatch.setenv("MAX_OPS_LLM_ENABLED", "0")
    monkeypatch.setenv("MAX_SPECIALISTS_CHANNEL_CHAT_ID", "-77768587291288")
    get_settings.cache_clear()
    bot = _SilentOps()
    body = (
        "Пенсионерам часто предлагают калькулятор стажа.\n"
        "Мы так не делаем: готовим документы и план, подаёте вы сами."
    )
    update = {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": 55},
            "body": {"text": body},
            "recipient": {"chat_id": 55},
        },
    }
    result = handle_ops_update(update, bot=bot)
    assert result.action == "chdraft_created"
    last = bot.sent[-1]
    assert last.get("user_id") == "55"
    assert last.get("chat_id") is None
    assert body.split("\n")[0] in last["text"]
    get_settings.cache_clear()


def test_channel_ignores_long_paste(monkeypatch) -> None:
    path = _draft_path()
    reset_draft_store(path)
    monkeypatch.setenv("MAX_OPS_LLM_ENABLED", "0")
    monkeypatch.setenv("MAX_SPECIALISTS_CHANNEL_CHAT_ID", "-77768587291288")
    get_settings.cache_clear()
    bot = _SilentOps()
    body = "x" * 130
    update = {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": 55},
            "body": {"text": body},
            "recipient": {"chat_id": -77768587291288},
        },
    }
    result = handle_ops_update(update, bot=bot)
    assert result.action == "ops_channel_ignore"
    get_settings.cache_clear()


def test_publish_callback(monkeypatch) -> None:
    path = _draft_path()
    reset_draft_store(path)
    get_draft_store(path).create(text="К публикации", draft_id="pub1")
    monkeypatch.setenv("MAX_CHANNEL_CHAT_ID", "-77580376877720")
    get_settings.cache_clear()
    bot = _SilentOps()

    def _fake_publish(draft, **_kw):  # noqa: ANN001
        get_draft_store().mark_published(draft.id, url="https://max.ru/pub", mid="mid9")
        return {"ok": True, "url": "https://max.ru/pub", "mid": "mid9", "draft_id": draft.id}

    monkeypatch.setattr(
        "sfrfr.integrations.max.channel_review.publish_draft_to_client_channel",
        _fake_publish,
    )
    update = {
        "update_type": "message_callback",
        "callback": {
            "callback_id": "cb1",
            "payload": "chdraft:pub:pub1",
            "user": {"user_id": 7},
        },
        "message": {"recipient": {"chat_id": -777}},
    }
    result = handle_ops_update(update, bot=bot)
    assert result.action == "chdraft_published"
    assert bot.sent[-1].get("chat_id") is None
    assert bot.sent[-1].get("user_id") == "7"
    get_settings.cache_clear()


def test_edit_callback_waits_in_dm(monkeypatch) -> None:
    path = _draft_path()
    reset_draft_store(path)
    get_draft_store(path).create(text="Правка", draft_id="e2")
    monkeypatch.setenv("MAX_OPS_LLM_ENABLED", "0")
    get_settings.cache_clear()
    bot = _SilentOps()
    update = {
        "update_type": "message_callback",
        "callback": {
            "callback_id": "cb2",
            "payload": "chdraft:edit:e2",
            "user": {"user_id": 9},
        },
        "message": {"recipient": {"chat_id": -777}},
    }
    result = handle_ops_update(update, bot=bot)
    assert result.action == "chdraft_edit_wait"
    assert "9" in get_draft_store().get("e2").waiting_edit_user_ids
    assert bot.sent[-1].get("chat_id") is None
    get_settings.cache_clear()
