"""Интеграционный срез E05/F04: адаптер → политика → outbox → mock MAX."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from sfrfr.services.max_e05_f04_path import (
    ACTION_E05_F04,
    deliver_policy_reply_via_outbox,
    try_policy_reply_for_case,
)
from sfrfr.services.max_sfrfr110_bridge import TrustedOpResult
from sfrfr.services.max_trusted_error_context import (
    ERROR_NOT_CONFIRMED_TEMPLATE,
    F04_UNCERTAINTY_TEMPLATE,
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


def _failed_limit(*, case_id: str) -> TrustedOpResult:
    return TrustedOpResult(
        case_id=case_id,
        operation_id="lim-1",
        op_kind="provisional_limit",
        ok=False,
        source="db_write_ack",
        version="v1",
        detail="apply_failed",
    )


def _ctx_f04(case_id: str = "case-a") -> TrustedErrorContext:
    return TrustedErrorContext(
        case_id=case_id,
        operation_id="op-err-1",
        error_confirmed=True,
        error_description="дате рождения в черновике",
        unknown_impact_area="итог проверки стажа",
        limit_op=_failed_limit(case_id=case_id),
        result_version="v1",
        authorized_for_case_id=case_id,
    )


def test_f04_handler_level_uncertainty_no_fake_limit() -> None:
    adapter = InMemoryTrustedErrorContextAdapter()
    adapter.put(_ctx_f04())
    reply = try_policy_reply_for_case(case_id="case-a", adapter=adapter)
    assert reply is not None
    assert reply.action == ACTION_E05_F04
    low = reply.text.casefold()
    assert "ошибка" in low
    assert "не буду сообщать, что исправление завершено" in low
    assert "результат ограничен" not in low
    assert "отметка установлена" not in low
    assert "всё исправлено" not in low
    expected = F04_UNCERTAINTY_TEMPLATE.format(
        error_description="дате рождения в черновике",
        impact_area="итог проверки стажа",
    )
    assert reply.text == expected


def test_error_not_confirmed_no_error_admission() -> None:
    adapter = InMemoryTrustedErrorContextAdapter()
    adapter.put(
        TrustedErrorContext(
            case_id="case-a",
            operation_id="op-1",
            error_confirmed=False,
            authorized_for_case_id="case-a",
        )
    )
    reply = try_policy_reply_for_case(case_id="case-a", adapter=adapter)
    assert reply is not None
    assert reply.text == ERROR_NOT_CONFIRMED_TEMPLATE
    assert "подтверждена ошибка" not in reply.text.casefold()


def test_foreign_case_confirmation_not_used() -> None:
    adapter = InMemoryTrustedErrorContextAdapter()
    adapter.put(
        TrustedErrorContext(
            case_id="case-other",
            operation_id="op-1",
            error_confirmed=True,
            error_description="секрет другого дела",
            unknown_impact_area="чужой результат",
            limit_op=_failed_limit(case_id="case-other"),
            authorized_for_case_id="case-other",
        )
    )
    reply = try_policy_reply_for_case(case_id="case-a", adapter=adapter)
    assert reply is None


def test_stale_version_does_not_confirm_current_fix() -> None:
    adapter = InMemoryTrustedErrorContextAdapter()
    adapter.put(
        TrustedErrorContext(
            case_id="case-a",
            operation_id="op-1",
            error_confirmed=True,
            error_description="старая ошибка",
            unknown_impact_area="итог",
            limit_op=_failed_limit(case_id="case-a"),
            result_version="v1",
            authorized_for_case_id="case-a",
        )
    )
    reply = try_policy_reply_for_case(
        case_id="case-a",
        adapter=adapter,
        current_result_version="v2",
    )
    assert reply is None


def test_model_invented_fixed_phrase_not_sent() -> None:
    adapter = InMemoryTrustedErrorContextAdapter()
    adapter.put(_ctx_f04())
    reply = try_policy_reply_for_case(
        case_id="case-a",
        adapter=adapter,
        invented_model_text="Всё исправлено, результат ограничен.",
    )
    assert reply is not None
    low = reply.text.casefold()
    assert "исправлено" not in low or "не буду сообщать, что исправление завершено" in low
    assert "всё исправлено" not in low
    assert "результат ограничен" not in low
    assert "использование ограничено" not in low


def test_fallback_strips_incompatible_buttons() -> None:
    adapter = InMemoryTrustedErrorContextAdapter()
    adapter.put(_ctx_f04())
    prior = [
        {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [[{"text": "Оплатить", "url": "https://example.com"}]]
            },
        }
    ]
    reply = try_policy_reply_for_case(
        case_id="case-a",
        adapter=adapter,
        prior_attachments=prior,
    )
    assert reply is not None
    assert reply.attachments == []


def test_null_adapter_does_not_intercept_production_path() -> None:
    reply = try_policy_reply_for_case(
        case_id="case-a",
        adapter=NullTrustedErrorContextAdapter(),
    )
    assert reply is None


def test_repeat_incoming_no_business_limit_side_effect() -> None:
    """Повтор события не ставит ограничение — путь только читает факты."""
    adapter = InMemoryTrustedErrorContextAdapter()
    adapter.put(_ctx_f04())
    r1 = try_policy_reply_for_case(case_id="case-a", adapter=adapter)
    r2 = try_policy_reply_for_case(case_id="case-a", adapter=adapter)
    assert r1 is not None and r2 is not None
    assert r1.text == r2.text
    # Срез не вызывает установку ограничения — только читает TrustedOpResult.
    assert r1.package is not None
    refs = " ".join(r1.package.evidence_refs)
    assert "lim-1" in refs
    assert "provisional_limit" in refs


def test_enqueue_failure_no_success_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = InMemoryTrustedErrorContextAdapter()
    adapter.put(_ctx_f04())
    reply = try_policy_reply_for_case(case_id="case-a", adapter=adapter)
    assert reply is not None

    monkeypatch.setattr(
        "sfrfr.services.case_chat_delivery.enqueue_max_delivery",
        lambda **_k: False,
    )
    outcome = deliver_policy_reply_via_outbox(
        case_id="case-a",
        max_user_id="42",
        reply=reply,
        process_now=True,
    )
    assert outcome["enqueued"] is False
    assert outcome["sent"] is False
    assert outcome["reason"] == "enqueue_failed"


def test_successful_enqueue_is_not_sent_or_read(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = InMemoryTrustedErrorContextAdapter()
    adapter.put(_ctx_f04())
    reply = try_policy_reply_for_case(case_id="case-a", adapter=adapter)
    assert reply is not None

    monkeypatch.setattr(
        "sfrfr.services.case_chat_delivery.enqueue_max_delivery",
        lambda **_k: True,
    )
    outcome = deliver_policy_reply_via_outbox(
        case_id="case-a",
        max_user_id="42",
        reply=reply,
        process_now=False,
    )
    assert outcome["enqueued"] is True
    assert outcome["sent"] is False
    assert outcome["reason"] == "enqueued_pending"


def test_mock_max_accepts_only_confirmed_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = InMemoryTrustedErrorContextAdapter()
    adapter.put(_ctx_f04())
    reply = try_policy_reply_for_case(case_id="case-a", adapter=adapter)
    assert reply is not None

    monkeypatch.setattr(
        "sfrfr.services.case_chat_delivery.enqueue_max_delivery",
        lambda **_k: True,
    )
    bot = MagicMock()
    bot.send_message.return_value = {"ok": True, "message_id": "m-1"}
    outcome = deliver_policy_reply_via_outbox(
        case_id="case-a",
        max_user_id="42",
        reply=reply,
        process_now=True,
        bot=bot,
    )
    assert outcome["enqueued"] is True
    assert outcome["sent"] is True
    assert outcome["transport"] == {"ok": True, "message_id": "m-1"}
    bot.send_message.assert_called_once()
    kwargs = bot.send_message.call_args.kwargs
    assert "исправление завершено" in kwargs["text"]
    assert "не буду сообщать" in kwargs["text"].casefold()


def test_reply_to_free_text_intercepts_when_adapter_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sfrfr.integrations.max.llm_chat import reply_to_free_text

    adapter = InMemoryTrustedErrorContextAdapter()
    adapter.put(_ctx_f04("case-wire"))
    set_trusted_error_context_adapter_for_tests(adapter)

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

    class _Intake:
        def step(self) -> str:
            return "whom"

        llm_turn_count = 0
        max_user_id = "42"

    text, attachments, action = reply_to_free_text(
        user_text="почему ошибка?",
        intake=_Intake(),
        case_id="case-wire",
        work={},
    )
    assert action == ACTION_E05_F04
    assert attachments == []
    assert "не буду сообщать, что исправление завершено" in text.casefold()


def test_model_persist_ok_flag_not_trusted_as_system_proof() -> None:
    adapter = InMemoryTrustedErrorContextAdapter()
    adapter.put(
        TrustedErrorContext(
            case_id="case-a",
            operation_id="op-1",
            error_confirmed=True,
            error_description="дате",
            unknown_impact_area="итог",
            limit_op=TrustedOpResult(
                case_id="case-a",
                operation_id="lim-llm",
                op_kind="provisional_limit",
                ok=True,
                source="llm_self_report",
            ),
            result_version="v1",
            authorized_for_case_id="case-a",
        )
    )
    reply = try_policy_reply_for_case(case_id="case-a", adapter=adapter)
    assert reply is not None
    assert reply.package is not None
    assert "limit_outcome:unknown" in " ".join(reply.package.evidence_refs)
    low = reply.text.casefold()
    assert "использование ограничено" not in low
    assert "отмечен как требующий проверки" not in low


def test_unknown_limit_outcome_no_success_or_confirmed_failure_claim() -> None:
    adapter = InMemoryTrustedErrorContextAdapter()
    adapter.put(
        TrustedErrorContext(
            case_id="case-a",
            operation_id="op-1",
            error_confirmed=True,
            error_description="дате",
            unknown_impact_area="итог проверки",
            limit_op=TrustedOpResult(
                case_id="case-a",
                operation_id="lim-u",
                op_kind="provisional_limit",
                ok=None,
                source="db_write_ack",
                detail="timeout_before_ack",
            ),
            result_version="v1",
            authorized_for_case_id="case-a",
        )
    )
    reply = try_policy_reply_for_case(case_id="case-a", adapter=adapter)
    assert reply is not None
    assert reply.package is not None
    refs = " ".join(reply.package.evidence_refs)
    assert "limit_outcome:unknown" in refs
    # unknown ≠ confirmed_failure: в тексте нет утверждения об отказе меры
    low = reply.text.casefold()
    assert "ограничение применено" not in low
    assert "использование ограничено" not in low
    assert "подтверждённый отказ ограничения" not in low
    assert "не буду сообщать, что исправление завершено" in low


def test_confirmed_failure_limit_distinct_from_unknown() -> None:
    adapter = InMemoryTrustedErrorContextAdapter()
    adapter.put(_ctx_f04())
    reply = try_policy_reply_for_case(case_id="case-a", adapter=adapter)
    assert reply is not None
    assert reply.package is not None
    assert "limit_outcome:confirmed_failure" in " ".join(reply.package.evidence_refs)


def test_transport_accepted_does_not_claim_outbox_persist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MAX принял сообщение; mock-path не сохраняет status=sent — риск отдельно."""
    adapter = InMemoryTrustedErrorContextAdapter()
    adapter.put(_ctx_f04())
    reply = try_policy_reply_for_case(case_id="case-a", adapter=adapter)
    assert reply is not None
    monkeypatch.setattr(
        "sfrfr.services.case_chat_delivery.enqueue_max_delivery",
        lambda **_k: True,
    )
    bot = MagicMock()
    bot.send_message.return_value = {"ok": True, "message_id": "m-2"}
    outcome = deliver_policy_reply_via_outbox(
        case_id="case-a",
        max_user_id="42",
        reply=reply,
        process_now=True,
        bot=bot,
    )
    stages = outcome["stages"]
    assert stages["enqueued"] is True
    assert stages["transport_accepted"] is True
    assert stages["outbox_marked_sent"] is False
    assert stages["read"] is False
    # Не маскируем: sent по транспорту ≠ полный persist-исход.
    assert outcome["sent"] is True


def test_wire_boundary_not_full_webhook_e2e() -> None:
    """Документированная граница: тест reply_to_free_text ≠ полный webhook E2E."""
    note = (
        "Проверка начинается после входной аутентификации и первичной "
        "маршрутизации; эти участки этим тестом не покрыты."
    )
    assert "аутентификации" in note
