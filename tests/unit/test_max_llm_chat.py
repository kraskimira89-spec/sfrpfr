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
    assert "лицевого счета" in low or "илс" in low
    assert "кабинет" in low
    assert "сайте" in low
    assert "только на сайте" in low or "кабинет на сайте" in low
    assert "не обещай кабинет внутри max" in low or "не обещай «кабинет в max»" in low
    assert "не получается" in low
    assert "получите" in low
    assert "по шагам" in low
    assert "полные фразы с глаголом" in low
    assert "пароль" in low or "смс" in low
    assert "вручную" in low
    assert "свободн" in low
    assert "остановил" in low
    assert "специалист" in low
    assert "этот чат" in low
    assert "электронн" in low or "трудов" in low
    assert "справка" in low
    assert "банковск" in low
    assert "12" in CLIENT_CHAT_SYSTEM
    assert "опек" in low or "дет" in low
    # Паттерны из DeepSeek-экспортов (безопасно для клиента)
    assert "сверка" in low
    assert "посчитайте" in low or "сколько будет пенсия" in low
    assert "илс есть" in low
    assert "трудовая есть" in low
    assert "льготн" in low or "северн" in low or "вредн" in low
    # Вторая волна DeepSeek → стратегия общения
    assert "пенсия уже назначена" in low or "пенсия уже есть" in low
    assert "работаете" in low or "ещё работаю" in low
    assert "суд" in low
    assert "прокуратур" in low or "прокурор" in low
    assert "pdf" in low or "порядк" in low
    assert "север/льгота" in low or "север/льгот" in low


def test_reply_fallback_when_llm_disabled(monkeypatch) -> None:
    monkeypatch.setenv("MAX_LLM_CHAT_ENABLED", "0")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    text, kb, action = reply_to_free_text(user_text="подскажите", intake=None)
    assert action == "free_text_nudge"
    assert "кнопк" in text.lower() or "удобнее" in text.lower() or "проверк" in text.lower()
    assert kb
    get_settings.cache_clear()
