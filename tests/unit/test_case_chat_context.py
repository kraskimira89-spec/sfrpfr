"""Контекст чата для LLM: история и стадия сделки."""

from __future__ import annotations

from sfrfr.services.case_chat_context import (
    author_label,
    build_client_llm_user_prompt,
    format_deal_context,
    format_thread_for_llm,
)


def test_author_label() -> None:
    assert author_label("client") == "Клиент"
    assert author_label("staff") == "Специалист"
    assert author_label("system") == "Бот"


def test_format_thread_for_llm() -> None:
    text = format_thread_for_llm(
        [
            {"author_kind": "client", "body": "Здравствуйте, не учли стаж"},
            {"author_kind": "system", "body": "Подскажите, есть ли выписка ИЛС?"},
            {"author_kind": "client", "body": "Да, ИЛС есть"},
        ]
    )
    assert "Клиент:" in text
    assert "Бот:" in text
    assert "ИЛС" in text


def test_format_deal_context_pay() -> None:
    ctx = format_deal_context(
        {
            "status_label": "Документы на проверке",
            "status_key": "docs_review",
            "now_need": "Оплатить диагностику",
            "cta_key": "pay",
            "cta_label": "Оплатить безопасно",
            "required_uploaded": 2,
            "required_total": 2,
            "sla_note": "до 1 рабочего дня",
            "order": {
                "title": "Диагностика",
                "amount_rub": 3000,
                "status_label": "Ожидает оплаты",
                "state": "pay",
                "can_pay": True,
            },
            "next_actions": ["Оплатить диагностику"],
        }
    )
    assert "3000" in ctx
    assert "можно оплатить: да" in ctx
    assert "pay" in ctx


def test_build_client_llm_user_prompt_includes_history() -> None:
    prompt = build_client_llm_user_prompt(
        channel="cabinet",
        user_text="Сколько стоит проверка?",
        work={"status_label": "Новое", "status_key": "consent", "now_need": "Согласие"},
        history=[{"author_kind": "client", "body": "Хочу проверить стаж"}],
    )
    assert "История переписки" in prompt
    assert "Хочу проверить стаж" in prompt
    assert "Сколько стоит" in prompt
    assert "can_pay" in prompt
