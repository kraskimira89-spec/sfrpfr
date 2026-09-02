"""Тесты salutation и вставки обращения в подсказки сотруднику."""

from __future__ import annotations

from sfrfr.services.staff_reply_suggest import (
    DOCS_CHANNEL_CANON,
    SYSTEM,
    _ensure_salutation,
    client_salutation,
)


def test_client_salutation_full_fio() -> None:
    assert client_salutation("Иванов Иван Иванович") == "Иван Иванович"


def test_client_salutation_name_only() -> None:
    assert client_salutation("Мария") == "Мария"
    assert client_salutation("Петров Пётр") == "Пётр"
    assert client_salutation("") == "Клиент"
    assert client_salutation(None) == "Клиент"


def test_ensure_salutation_prepends_name() -> None:
    out = _ensure_salutation("Подскажите, когда удобно созвониться?", "Иван Иванович")
    assert out.startswith("Иван Иванович,")
    assert "созвониться" in out


def test_ensure_salutation_keeps_existing() -> None:
    text = "Здравствуйте, Иван Иванович! Документы получили."
    assert _ensure_salutation(text, "Иван Иванович") == text


def test_ensure_salutation_fixes_zdravstvuyte() -> None:
    out = _ensure_salutation("Здравствуйте! Ждём ИЛС.", "Мария Петровна")
    assert out.startswith("Здравствуйте, Мария Петровна!")
    assert "Ждём ИЛС" in out


def test_system_docs_channel_canon_max_chat() -> None:
    """Подсказки: чат MAX и кабинет на сайте; не «только в ЛК»."""
    assert "чат MAX" in DOCS_CHANNEL_CANON
    assert "cabinet.proverkastaza.ru" in DOCS_CHANNEL_CANON
    assert "загружайте только в личный кабинет" in DOCS_CHANNEL_CANON
    assert "Не пиши «загружайте только в личный кабинет»" in DOCS_CHANNEL_CANON
    assert DOCS_CHANNEL_CANON in SYSTEM
    assert "этот чат MAX" in SYSTEM
    assert "без обещаний перерасчёта" in SYSTEM
    assert "личн" in DOCS_CHANNEL_CANON.lower()
    assert "альтернатив" in DOCS_CHANNEL_CANON.lower() or "Также можно" in DOCS_CHANNEL_CANON


def test_suggest_replies_fallback_when_llm_errors(monkeypatch) -> None:
    class Fake:
        available = True

        def chat(self, **_kwargs):
            raise RuntimeError("401 AuthenticationError")

    monkeypatch.setattr(
        "sfrfr.services.staff_reply_suggest.LLMClient.for_analyze",
        classmethod(lambda cls, **kwargs: Fake()),
    )
    from sfrfr.services.staff_reply_suggest import suggest_staff_replies

    out = suggest_staff_replies(
        messages=[{"author_kind": "client", "body": "Здравствуйте, хочу проверить стаж"}],
        pipeline_status="intake",
        b2c_status="lead",
        client_name="Иванов Иван Иванович",
    )
    assert len(out) >= 2
    assert all(isinstance(s, str) and s.strip() for s in out)
