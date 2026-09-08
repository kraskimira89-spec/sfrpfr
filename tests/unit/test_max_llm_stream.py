"""ТЗ-26: preview стрима и edit_message клиента MAX."""

from __future__ import annotations

from unittest.mock import MagicMock

from sfrfr.integrations.max.client import MaxBotClient
from sfrfr.integrations.max.llm_chat import stream_preview_text


def test_stream_preview_strips_buttons_and_adds_ellipsis() -> None:
    raw = "REPLY: Здравствуйте, давайте сверим ИЛС\nBUTTONS: Есть ИЛС | Нет ИЛС"
    preview = stream_preview_text(raw)
    assert "Здравствуйте" in preview
    assert "BUTTONS" not in preview
    assert preview.endswith("…")


def test_stream_preview_without_reply_prefix() -> None:
    preview = stream_preview_text("Частичный текст без метки\nBUTTONS: A | B")
    assert preview.startswith("Частичный")
    assert "BUTTONS" not in preview


def test_edit_message_puts_messages(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResp:
        content = b'{"success": true}'
        def raise_for_status(self) -> None:
            return None
        def json(self) -> dict:
            return {"success": True}

    class FakeHttp:
        def __enter__(self) -> FakeHttp:
            return self
        def __exit__(self, *args: object) -> None:
            return None
        def put(self, url: str, **kwargs: object) -> FakeResp:
            captured["url"] = url
            captured["params"] = kwargs.get("params")
            captured["json"] = kwargs.get("json")
            return FakeResp()

    client = MaxBotClient(token="t", api_base="https://platform-api2.max.ru")
    monkeypatch.setattr(client, "_client", lambda: FakeHttp())
    out = client.edit_message(message_id="mid-1", text="Привет", notify=False)
    assert out.get("success") is True
    assert captured["url"] == "https://platform-api2.max.ru/messages"
    assert captured["params"] == {"message_id": "mid-1"}
    assert captured["json"] == {"notify": False, "text": "Привет"}


def test_deliver_uses_edit_when_stream_sends_placeholder(monkeypatch) -> None:
    from sfrfr.core.config import get_settings
    from sfrfr.integrations.max import llm_chat

    get_settings.cache_clear()
    monkeypatch.setenv("MAX_LLM_CHAT_ENABLED", "1")
    monkeypatch.setenv("MAX_LLM_STREAM_EDIT_ENABLED", "1")
    monkeypatch.setenv("MAX_LLM_TYPING_PULSE_ENABLED", "0")
    get_settings.cache_clear()

    bot = MagicMock()
    bot.send_chat_action.return_value = {"ok": True}
    bot.send_message.return_value = {"message": {"mid": "m-stream"}}
    bot.edit_message.return_value = {"success": True}

    def fake_reply(**kwargs):
        on_partial = kwargs.get("on_partial")
        assert kwargs.get("stream") is True
        assert callable(on_partial)
        on_partial("REPLY: Черновик ответа")
        return (
            "Готовый ответ\n\nМожно ответить кнопками ниже.",
            [],
            "max_llm_reply",
        )

    monkeypatch.setattr(llm_chat, "reply_to_free_text", fake_reply)

    text, _att, action = llm_chat.deliver_free_text_reply(
        bot=bot,
        user_id="1",
        chat_id=42,
        user_text="подскажите",
        intake=None,
    )
    assert action == "max_llm_reply"
    assert "Готовый" in text
    assert bot.send_message.call_count == 1  # placeholder only
    assert bot.edit_message.call_count >= 1  # final (+ maybe intermediate)
    # Финальный edit — полный текст
    final_edit = bot.edit_message.call_args_list[-1]
    assert "Готовый ответ" in str(final_edit)
    get_settings.cache_clear()
