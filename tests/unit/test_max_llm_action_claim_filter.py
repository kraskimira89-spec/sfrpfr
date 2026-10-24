"""Постфильтр max_llm_reply: неподтверждённые утверждения о действиях."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from sfrfr.services.max_llm_action_claim_filter import (
    ACTION_CLAIM_SAFE_FALLBACK,
    FILTER_VERSION,
    filter_llm_action_claims,
)
from sfrfr.services.max_sfrfr110_bridge import TrustedOpResult
from sfrfr.services.max_trusted_error_context import (
    InMemoryTrustedErrorContextAdapter,
    NullTrustedErrorContextAdapter,
    TrustedErrorContext,
    set_trusted_error_context_adapter_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_adapter() -> Any:
    set_trusted_error_context_adapter_for_tests(NullTrustedErrorContextAdapter())
    yield
    set_trusted_error_context_adapter_for_tests(None)


def test_null_llm_date_fixed_claim_not_sent() -> None:
    out = filter_llm_action_claims(
        text="Дата исправлена в деле. Всё готово.",
        attachments=[{"type": "inline_keyboard", "payload": {}}],
        case_id="case-a",
        adapter=NullTrustedErrorContextAdapter(),
    )
    assert out.blocked is True
    assert out.text == ACTION_CLAIM_SAFE_FALLBACK
    assert out.attachments == []
    assert "дата исправлена" not in out.text.casefold()


def test_empty_policy_then_llm_same_protection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Пустой policy → LLM-путь; тот же фильтр."""
    from sfrfr.integrations.max.llm_chat import reply_to_free_text
    from sfrfr.services.max_e05_f04_path import PolicyReply

    monkeypatch.setattr(
        "sfrfr.integrations.max.llm_chat.llm_chat_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_context.staff_dialog_active",
        lambda _h: False,
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_context.fetch_recent_case_messages",
        lambda *_a, **_k: [],
    )
    # Пустой policy-text → coerce → None → LLM
    monkeypatch.setattr(
        "sfrfr.services.max_e05_f04_path.try_policy_reply_for_case",
        lambda **_k: PolicyReply(text="   ", action="max_e05_f04_policy"),
    )

    class _FakeLLM:
        available = True
        model = "fake"

        def chat(self, *_a: Any, **_k: Any) -> str:
            return "Дата исправлена."

    monkeypatch.setattr(
        "sfrfr.integrations.max.llm_chat.LLMClient.for_analyze",
        lambda **_k: _FakeLLM(),
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_context.build_client_context_pack",
        lambda **_k: {},
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_context.build_client_llm_user_prompt",
        lambda **_k: "u",
    )
    monkeypatch.setattr(
        "sfrfr.services.position_throttle.apply_position_policy",
        lambda text, **_k: text,
    )

    class _Intake:
        def step(self) -> str:
            return "whom"

        llm_turn_count = 0
        max_user_id = "42"

    text, atts, action = reply_to_free_text(
        user_text="когда исправите?",
        intake=_Intake(),
        case_id="case-empty-policy",
        work={},
    )
    assert action == "max_llm_reply"
    assert "дата исправлена" not in text.casefold()
    assert "не буду сообщать, что исправление завершено" in text.casefold()
    assert atts == [] or all(
        str(a.get("type") or "") not in {"inline_keyboard", "keyboard"} for a in atts
    )


def test_limit_claim_without_confirmation_blocked() -> None:
    out = filter_llm_action_claims(
        text="Результат ограничен. Использование ограничено.",
        case_id="case-a",
    )
    assert out.blocked is True
    assert "ограничен" not in out.text.casefold() or "не буду" in out.text.casefold()


def test_offer_to_help_not_treated_as_completed_action() -> None:
    text = "Я могу помочь проверить дату в выписке. Можем вместе уточнить период."
    out = filter_llm_action_claims(text=text, case_id="case-a")
    assert out.blocked is False
    assert out.text == text


def test_client_quote_not_system_confirmation() -> None:
    text = 'Вы написали: «дату исправили». Пока это не подтверждено системой.'
    out = filter_llm_action_claims(text=text, case_id="case-a")
    assert out.blocked is False
    assert "вы написали" in out.text.casefold()


def test_foreign_case_or_stale_version_does_not_allow_claim() -> None:
    adapter = InMemoryTrustedErrorContextAdapter()
    adapter.put(
        TrustedErrorContext(
            case_id="case-other",
            operation_id="op-1",
            error_confirmed=True,
            error_description="дате",
            unknown_impact_area="итог",
            limit_op=TrustedOpResult(
                case_id="case-other",
                operation_id="lim",
                op_kind="provisional_limit",
                ok=True,
                source="db_write_ack",
            ),
            result_version="v1",
            authorized_for_case_id="case-other",
        )
    )
    out = filter_llm_action_claims(
        text="Использование ограничено.",
        case_id="case-a",
        adapter=adapter,
        current_result_version="v1",
    )
    assert out.blocked is True

    adapter2 = InMemoryTrustedErrorContextAdapter()
    adapter2.put(
        TrustedErrorContext(
            case_id="case-a",
            operation_id="op-1",
            error_confirmed=True,
            error_description="дате",
            unknown_impact_area="итог",
            limit_op=TrustedOpResult(
                case_id="case-a",
                operation_id="lim",
                op_kind="provisional_limit",
                ok=True,
                source="db_write_ack",
            ),
            result_version="v1",
            authorized_for_case_id="case-a",
        )
    )
    out_stale = filter_llm_action_claims(
        text="Использование ограничено.",
        case_id="case-a",
        adapter=adapter2,
        current_result_version="v2",
    )
    assert out_stale.blocked is True


def test_fallback_strips_incompatible_buttons() -> None:
    out = filter_llm_action_claims(
        text="Всё исправлено.",
        attachments=[
            {
                "type": "inline_keyboard",
                "payload": {"buttons": [[{"text": "Оплатить"}]]},
            }
        ],
        case_id="case-a",
    )
    assert out.blocked is True
    assert out.attachments == []


def test_filter_exception_returns_safe_not_raw(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sfrfr.services.max_llm_action_claim_filter._scan_completed_action_claims",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    raw = "Дата исправлена и всё готово."
    out = filter_llm_action_claims(text=raw, case_id="case-a")
    assert out.blocked is True
    assert out.text == ACTION_CLAIM_SAFE_FALLBACK
    assert out.text != raw
    assert out.reason == "filter_error"


def test_repeat_delivery_does_not_regenerate_different_meaning() -> None:
    """Повтор фильтра стабилен: без новой LLM-генерации."""
    text = "Дата исправлена."
    a = filter_llm_action_claims(text=text, case_id="case-a")
    b = filter_llm_action_claims(text=text, case_id="case-a")
    assert a.text == b.text == ACTION_CLAIM_SAFE_FALLBACK
    assert a.filter_version == b.filter_version == FILTER_VERSION


def test_saved_and_sent_match_filtered_version(monkeypatch: pytest.MonkeyPatch) -> None:
    from sfrfr.services.max_e05_f04_path import (
        PolicyReply,
        deliver_policy_reply_via_outbox,
    )

    filtered = filter_llm_action_claims(
        text="Дата исправлена.",
        case_id="case-a",
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_delivery.enqueue_max_delivery",
        lambda **_k: True,
    )
    bot = MagicMock()
    bot.send_message.return_value = {"ok": True, "message_id": "m-1"}
    outcome = deliver_policy_reply_via_outbox(
        case_id="case-a",
        max_user_id="42",
        reply=PolicyReply(text=filtered.text, attachments=list(filtered.attachments)),
        process_now=True,
        bot=bot,
    )
    assert outcome["sent"] is True
    sent_text = bot.send_message.call_args.kwargs["text"]
    assert sent_text == filtered.text
    assert "дата исправлена" not in sent_text.casefold()


def test_negation_and_uncertainty_not_blocked() -> None:
    text = (
        "Я не буду сообщать, что исправление завершено. "
        "Пока не установлено, исправлена ли дата."
    )
    out = filter_llm_action_claims(text=text, case_id="case-a")
    assert out.blocked is False
    assert out.text == text
