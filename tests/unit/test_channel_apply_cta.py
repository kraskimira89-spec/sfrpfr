"""CTA постов канала: всегда «Подать заявку» → чат."""

from __future__ import annotations

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.channel_drafts import (
    DEFAULT_APPLY_CTA_LABEL,
    ChannelDraft,
    client_cta_attachments,
)


def test_apply_cta_always_when_chat_url(monkeypatch) -> None:
    monkeypatch.setenv("MAX_CHAT_URL", "https://max.ru/bot_test")
    get_settings.cache_clear()
    draft = ChannelDraft(id="d1", text="hello", cta_label="", cta_kind="")
    att = client_cta_attachments(draft)
    assert att is not None
    buttons = att[0]["payload"]["buttons"]
    assert buttons[0][0]["text"] == DEFAULT_APPLY_CTA_LABEL
    assert buttons[0][0]["url"] == "https://max.ru/bot_test"


def test_url_post_gets_apply_plus_site(monkeypatch) -> None:
    monkeypatch.setenv("MAX_CHAT_URL", "https://max.ru/bot_test")
    get_settings.cache_clear()
    draft = ChannelDraft(
        id="d2",
        text="hello",
        cta_label="Как читать ИЛС на сайте",
        cta_kind="url",
        cta_url="https://proverkastaza.ru/blog/ils/",
    )
    att = client_cta_attachments(draft)
    assert att is not None
    buttons = att[0]["payload"]["buttons"]
    assert len(buttons) == 2
    assert buttons[0][0]["text"] == DEFAULT_APPLY_CTA_LABEL
    assert buttons[0][0]["url"] == "https://max.ru/bot_test"
    assert buttons[1][0]["text"] == "Как читать ИЛС на сайте"
    assert "proverkastaza.ru" in buttons[1][0]["url"]


def test_legacy_chat_label_normalized_to_apply(monkeypatch) -> None:
    monkeypatch.setenv("MAX_CHAT_URL", "https://max.ru/bot_test")
    get_settings.cache_clear()
    draft = ChannelDraft(
        id="d3",
        text="hello",
        cta_label="Уточнить ситуацию в MAX",
        cta_kind="chat",
    )
    att = client_cta_attachments(draft)
    buttons = att[0]["payload"]["buttons"]
    assert buttons[0][0]["text"] == DEFAULT_APPLY_CTA_LABEL
