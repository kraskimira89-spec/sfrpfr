from sfrfr.services.full_analysis_draft import (
    build_template_draft,
    generate_full_analysis_draft,
)


def test_template_draft_has_structure_and_position() -> None:
    text = build_template_draft(
        case_ref="ПС-123",
        documents=[{"doc_type": "ils", "filename": "ils.pdf"}],
        brief={
            "items": [
                {
                    "text": "Период 2004–2005 отсутствует в ИЛС",
                    "evidence": "docs",
                    "basis": "Трудовая vs выписка",
                }
            ]
        },
        compare={"ran": True, "discrepancies": 1, "summary": "1 расхождение."},
    )
    assert "Подробный разбор" in text
    assert "ils.pdf" in text
    assert "Период 2004" in text
    assert "Решение принимает СФР" in text
    assert "гарантируем" not in text.lower()
    assert "₽ в месяц" not in text.lower()


def test_generate_falls_back_without_llm() -> None:
    out = generate_full_analysis_draft(
        case_ref="ПС-1",
        documents=[],
        brief={"items": []},
        llm=None,
    )
    assert out["source"] == "template"
    assert "Решение принимает СФР" in out["text"]


class _FakeLLM:
    available = True
    provider = "yandex"
    last_provider_used = "yandex"
    last_used_fallback = False

    def chat(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.last_provider_used = "yandex"
        self.last_used_fallback = False
        return (
            "# Подробный разбор\n\n"
            "Изучили выписку ИЛС и трудовую.\n\n"
            "## Расхождения\n1. Период не отражён.\n\n"
            "Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. "
            "Решение принимает СФР."
        )


def test_generate_uses_ai_when_valid() -> None:
    out = generate_full_analysis_draft(
        case_ref="ПС-2",
        documents=[{"doc_type": "ils", "filename": "a.pdf"}],
        brief={"items": [{"text": "Период не отражён", "evidence": "docs"}]},
        llm=_FakeLLM(),
    )
    assert out["source"] == "ai"
    assert "Период не отражён" in out["text"]
    assert out.get("llm_provider") == "yandex"
    assert out.get("llm_fallback") is False


class _FallbackLLM:
    available = True
    provider = "yandex"
    last_provider_used = "deepseek"
    last_used_fallback = True

    def chat(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.last_provider_used = "deepseek"
        self.last_used_fallback = True
        return (
            "# Подробный разбор\n\n"
            "Изучили выписку ИЛС и трудовую.\n\n"
            "## Расхождения\n1. Период не отражён.\n\n"
            "Решение принимает СФР."
        )


def test_generate_reports_fallback_provider() -> None:
    out = generate_full_analysis_draft(
        case_ref="ПС-2b",
        documents=[{"doc_type": "ils", "filename": "a.pdf"}],
        brief={"items": [{"text": "Период не отражён", "evidence": "docs"}]},
        llm=_FallbackLLM(),
    )
    assert out["source"] == "ai"
    assert out.get("llm_provider") == "deepseek"
    assert out.get("llm_fallback") is True


class _PromiseLLM:
    available = True

    def chat(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        return "Гарантируем перерасчёт пенсии на 5000 ₽ в месяц после обращения."


def test_generate_rejects_promise() -> None:
    out = generate_full_analysis_draft(
        case_ref="ПС-3",
        documents=[],
        brief={"items": [{"text": "x", "evidence": "docs"}]},
        llm=_PromiseLLM(),
    )
    assert out["source"] == "template"
    assert out.get("reason") == "promise"
