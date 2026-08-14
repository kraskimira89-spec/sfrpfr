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
    assert parse_draft_callback("other") is None
    kb = review_keyboard(draft)
    buttons = kb[0]["payload"]["buttons"]
    assert buttons[0][0]["text"] == "Опубликовать"
    assert buttons[1][0]["type"] == "clipboard"
    assert len(buttons) == 2
    msg = format_review_message(draft)
    assert "07-no-calc" in msg
    assert "Текст поста" in msg


def test_edit_wait_and_resubmit(monkeypatch) -> None:
    path = _draft_path()
    reset_draft_store(path)
    get_draft_store(path).create(text="Старый текст", draft_id="ed1")
    get_draft_store().mark_waiting_edit("ed1", "42")

    monkeypatch.setenv("MAX_OPS_LLM_ENABLED", "0")
    get_settings.cache_clear()
    bot = _SilentOps()
    update = {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": 42},
            "body": {"text": "Новый текст поста"},
            "recipient": {"chat_id": -100},
        },
    }
    result = handle_ops_update(update, bot=bot)
    assert result.action == "chdraft_updated"
    updated = get_draft_store().get("ed1")
    assert updated is not None
    assert updated.text == "Новый текст поста"
    assert "Опубликовать" in str(bot.sent[-1].get("attachments"))
    get_settings.cache_clear()


def test_publish_callback(monkeypatch) -> None:
    path = _draft_path()
    reset_draft_store(path)
    get_draft_store(path).create(
        text="К публикации",
        draft_id="pub1",
        cta_label="Уточнить",
        cta_kind="chat",
    )
    monkeypatch.setenv("MAX_CHANNEL_CHAT_ID", "-77580376877720")
    monkeypatch.setenv("MAX_CHAT_URL", "https://max.ru/u/x")
    get_settings.cache_clear()

    bot = _SilentOps()
    published: list[dict] = []

    def _fake_publish(draft, **_kw):  # noqa: ANN001
        published.append({"id": draft.id, "text": draft.text})
        get_draft_store().mark_published(draft.id, url="https://max.ru/pub", mid="mid9")
        return {
            "ok": True,
            "url": "https://max.ru/pub",
            "mid": "mid9",
            "draft_id": draft.id,
        }

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
    assert published and published[0]["id"] == "pub1"
    assert get_draft_store().get("pub1").status == "published"
    assert bot.answers and "Публикуем" in (bot.answers[0].get("notification") or "")
    get_settings.cache_clear()


def test_edit_callback_removed(monkeypatch) -> None:
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
    assert result.action == "chdraft_edit_removed"
    assert any("отключена" in (m.get("text") or "") for m in bot.sent)
    get_settings.cache_clear()
