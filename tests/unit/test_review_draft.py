"""Тесты черновика отзыва по анкете."""

from __future__ import annotations

from sfrfr.core.review_draft import build_review_draft, question_catalog, template_draft


def test_question_catalog_has_three() -> None:
    cats = question_catalog()
    assert len(cats) == 3
    assert cats[0]["id"] == "helped"


def test_template_draft_builds_text() -> None:
    text = template_draft(
        {"helped": ["ils_labor", "plan"], "clarity": "yes", "convenient": ["max", "steps"]}
    )
    assert "Проверка стажа" in text
    assert "илс" in text.lower() or "сверил" in text.lower() or "план" in text.lower()


def test_build_review_draft_needs_answers() -> None:
    result = build_review_draft({"helped": "plan"})
    assert result["ok"] is False


def test_build_review_draft_ok_template_or_llm(monkeypatch) -> None:
    # Без реального LLM — template fallback
    from sfrfr.ai import llm as llm_mod

    class Fake:
        available = False

        def chat(self, **kwargs):  # noqa: ANN003
            return ""

    monkeypatch.setattr(llm_mod.LLMClient, "for_draft", classmethod(lambda cls, **k: Fake()))
    result = build_review_draft(
        {"helped": ["plan"], "clarity": "mostly", "convenient": ["steps"]}
    )
    assert result["ok"] is True
    assert result["draft"]
    assert result["publish_url"].endswith("/otzyv/")
    assert result["source"] == "template"
