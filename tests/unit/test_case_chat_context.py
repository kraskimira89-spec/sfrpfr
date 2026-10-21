"""Контекст чата для LLM: история и стадия сделки."""

from __future__ import annotations

from types import SimpleNamespace

from sfrfr.services.case_chat_context import (
    author_label,
    build_client_context_pack,
    build_client_llm_user_prompt,
    format_context_pack_for_prompt,
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
    assert "ContextPack" in prompt
    assert "can_pay" in prompt


def test_context_pack_lists_confirmed_intake_without_raw_phone() -> None:
    intake = SimpleNamespace(
        q_answers={"experience": "10_20", "phone": "+79001234567", "problem": "не учли стаж"},
        q_completed_at="2026-10-21T10:00:00Z",
        q_step=None,
        goal="ils_stazh",
        for_whom="self",
        pension_status="assigned",
        problem_type="ils_stazh",
        ils_available="yes",
        employment_records_available=None,
        step=lambda: "summary",
    )
    pack = build_client_context_pack(
        channel="max",
        user_text="Что дальше?",
        work={"cta_key": "docs_max", "now_need": "Прислать трудовую"},
        history=[],
        intake=intake,
        consent_accepted=True,
    )
    blob = format_context_pack_for_prompt(pack)
    assert "телефон: указан" in blob
    assert "79001234567" not in blob
    assert "не учли стаж" in blob
    assert "Уже известно" in blob
    prompt = build_client_llm_user_prompt(
        channel="max",
        user_text="Что дальше?",
        work={"cta_key": "docs_max", "now_need": "Прислать трудовую"},
        intake=intake,
        context_pack=pack,
    )
    assert "не спрашивай повторно" in prompt.lower()


def test_context_pack_marks_pending_and_forbids_fake_analysis() -> None:
    pack = build_client_context_pack(
        channel="max",
        user_text="Вы изучили мой PDF?",
        work={"required_uploaded": 0, "required_total": 2, "cta_key": "docs_max"},
        history=[],
        documents=[
            {
                "id": "d1",
                "doc_type": "ils",
                "ingest_status": "needs_reupload",
                "cloud_status": "pending",
            }
        ],
        consent_accepted=True,
    )
    prompt = build_client_llm_user_prompt(
        channel="max",
        user_text="Вы изучили мой PDF?",
        work=pack["work"],
        context_pack=pack,
    )
    low = prompt.lower()
    assert "pending" in low or "ожидает" in low
    assert "не передано" in low or "содержание документов модели не передано" in low
    assert "не говори «документ изучен" in low or "не говори" in low
