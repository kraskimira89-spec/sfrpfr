"""ТЗ-26: DeepSeek-чат MAX и парсинг кнопок."""

from __future__ import annotations

from sfrfr.integrations.max.llm_chat import _parse_llm_payload, looks_like_pdn, reply_to_free_text


def test_parse_llm_payload_with_buttons() -> None:
    reply, buttons = _parse_llm_payload(
        "REPLY: Здравствуйте, выберите шаг ниже.\nBUTTONS: Есть ИЛС | Нет ИЛС | Специалист"
    )
    assert "Здравствуйте" in reply
    assert buttons == ["Есть ИЛС", "Нет ИЛС", "Специалист"]


def test_looks_like_pdn() -> None:
    assert looks_like_pdn("мой снилс 123-456-789 00") is True
    assert looks_like_pdn("где взять ИЛС?") is False


def test_client_chat_system_prompt_rules() -> None:
    from sfrfr.integrations.max.llm_chat import CLIENT_CHAT_SYSTEM

    low = CLIENT_CHAT_SYSTEM.lower()
    assert "сфр" in low
    assert "3 000" in CLIENT_CHAT_SYSTEM or "3000" in CLIENT_CHAT_SYSTEM.replace(" ", "")
    assert "кнопк" in low
    assert "снилс" in low or "скан" in low
    assert "reply:" in low
    assert "зачем" in low or "чтобы" in low
    assert "не обещай" in low or "не обеща" in low


def test_reply_fallback_when_llm_disabled(monkeypatch) -> None:
    monkeypatch.setenv("MAX_LLM_CHAT_ENABLED", "0")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    text, kb, action = reply_to_free_text(user_text="подскажите", intake=None)
    assert action == "free_text_nudge"
    assert "кнопк" in text.lower() or "удобнее" in text.lower() or "проверк" in text.lower()
    assert kb
    get_settings.cache_clear()
