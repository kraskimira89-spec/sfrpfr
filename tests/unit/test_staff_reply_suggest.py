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
    """Подсказки сотруднику: только чат MAX; без кабинета и повторного согласия."""
    low = DOCS_CHANNEL_CANON.lower()
    assert "чат MAX" in DOCS_CHANNEL_CANON
    assert "cabinet.proverkastaza.ru" not in DOCS_CHANNEL_CANON
    assert "не проси согласие" in low
    assert "Не предлагай личный кабинет" in DOCS_CHANNEL_CANON
    assert DOCS_CHANNEL_CANON in SYSTEM
    assert "этот чат MAX" in SYSTEM
    assert "без обещаний перерасчёта" in SYSTEM
    assert "согласие" in low
    assert "начать" in low


def test_suggest_replies_depersonalized_prompt_name_restored(monkeypatch) -> None:
    """Резерв DeepSeek вне РФ: ФИО не уходит в промпт, имя подставляем у себя."""
    seen: dict = {}

    class Fake:
        available = True

        def chat(self, *, system: str, user: str, temperature: float = 0.0) -> str:
            seen["user"] = user
            return (
                "1) Здравствуйте, {ИМЯ}! Пришлите выписку ИЛС в этот чат.\n"
                "2) {ИМЯ}, пришлите выписку ИЛС и трудовую в этот чат.\n"
                "3) Здравствуйте, {ИМЯ}! Ждём трудовую книжку."
            )

    def fake_for_analyze(cls, **kwargs):
        seen["kwargs"] = kwargs
        return Fake()

    monkeypatch.setattr(
        "sfrfr.services.staff_reply_suggest.LLMClient.for_analyze",
        classmethod(fake_for_analyze),
    )
    from sfrfr.services.staff_reply_suggest import suggest_staff_replies

    out = suggest_staff_replies(
        messages=[
            {"author_kind": "staff", "body": "Здравствуйте, Иван Иванович! Пришлите ИЛС."},
            {"author_kind": "client", "body": "Иванов Иван Иванович, не учли стаж"},
        ],
        pipeline_status="intake",
        b2c_status="lead",
        client_name="Иванов Иван Иванович",
    )
    assert seen["kwargs"].get("foreign_ok") is True
    assert "Иван" not in seen["user"]
    assert "Иванов" not in seen["user"]
    assert all("{ИМЯ}" not in s for s in out)
    assert out[0].startswith("Здравствуйте, Иван Иванович!")


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
    joined = " ".join(out).lower()
    assert "кабинет" not in joined
    assert "cabinet.proverkastaza.ru" not in joined
    assert "согласи" not in joined

def test_suggest_replies_includes_ops_facts(monkeypatch) -> None:
    seen: dict = {}

    class Fake:
        available = True

        def chat(self, *, system: str, user: str, temperature: float = 0.0) -> str:
            seen["user"] = user
            return (
                "1) {ИМЯ}, готовим письменный разбор по отмеченным периодам.\n"
                "2) {ИМЯ}, диагностика оплачена.\n"
                "3) {ИМЯ}, напишите, если остались вопросы."
            )

    monkeypatch.setattr(
        "sfrfr.services.staff_reply_suggest.LLMClient.for_analyze",
        classmethod(lambda cls, **kwargs: Fake()),
    )
    from sfrfr.services.staff_reply_suggest import suggest_staff_replies

    out = suggest_staff_replies(
        messages=[{"author_kind": "client", "body": "хорошо"}],
        pipeline_status="human_review",
        client_name="Иванов Иван Иванович",
        ops_facts={
            "check_status": "completed",
            "discrepancies": ["Северный стаж учтён не за весь период"],
            "compare_summary": "найдено расхождений: 1.",
            "diag_paid": True,
            "diag_pending": False,
            "support_or_accomp_pending": True,
            "support_or_accomp_paid": False,
            "staff_next": "prepare_analysis",
            "unique_documents": 3,
        },
    )
    assert "DIAG оплачен" in seen["user"]
    assert "prepare_analysis" in seen["user"]
    assert "Северный стаж" in seen["user"]
    assert out and "Иван Иванович" in out[0]
