"""SFRFR-110: отрицательные и составные запреты §69–72 (библиотека политик)."""

from __future__ import annotations

from sfrfr.services.deception_client_reply_policy import (
    SAFE_INCOMPLETE_FACTS_FALLBACK,
    ConfirmedErrorReplyKind,
    build_confirmed_error_reply,
    client_facing_error_reply,
    may_say_fixed_before_persist,
    persist_flag_is_trusted,
    reply_has_banned_internal_labels,
)
from sfrfr.services.deception_evidence_contract import (
    may_tech_fix_close_finance_claim,
)
from sfrfr.services.deception_transition_refine import (
    announce_fix_allowed,
    may_announce_fixed_on_partial_persist_failure,
    may_create_duplicate_claim_on_retry,
    may_invent_evidence_ref_when_store_failed,
    may_treat_read_as_acceptance,
    may_treat_sent_as_read,
)


def test_persist_not_done_forbids_fixed_wording() -> None:
    assert may_say_fixed_before_persist() is False
    got = build_confirmed_error_reply(
        ConfirmedErrorReplyKind.PERIOD,
        facts={
            "wrong_fact": "1987",
            "confirmed_correction": "1985",
            "date_persist_succeeded": False,
        },
    )
    assert "Дата исправлена в деле" not in got["text"]
    assert announce_fix_allowed(
        persist_ok=False, cause_fixed=True, consequences_checked=True
    )["may_say_fixed"] is False
    assert may_announce_fixed_on_partial_persist_failure() is False


def test_llm_persist_flag_not_trusted() -> None:
    assert persist_flag_is_trusted(source="llm_self_report", value=True) is False
    assert persist_flag_is_trusted(source="prompt_filled_flag", value=True) is False
    assert persist_flag_is_trusted(source="db_write_ack", value=True) is True
    facing = client_facing_error_reply(
        ConfirmedErrorReplyKind.PERIOD,
        facts={
            "wrong_fact": "1987 году",
            "confirmed_correction": "1985 год",
            "date_persist_succeeded": True,
        },
        persist_source="llm_self_report",
    )
    # без trusted persist → date_persist_succeeded=False → текст без «исправлена в деле»
    assert facing["ok"] is True
    assert "Дата исправлена в деле" not in facing["text"]


def test_unknown_outcome_no_blind_retry_signal() -> None:
    # контракт: неизвестный исход → сверка; библиотека не инициирует повтор
    assert may_invent_evidence_ref_when_store_failed() is False
    facing = client_facing_error_reply(
        ConfirmedErrorReplyKind.FALSE_CHECK_RUNNING,
        facts={},  # нет actual_status
    )
    assert facing["fallback"] is True
    assert "завершено" in facing["text"].casefold()
    assert "повторно запускаю" not in facing["text"].casefold()


def test_cause_fixed_consequences_open_blocks_full_done() -> None:
    partial = announce_fix_allowed(
        persist_ok=True, cause_fixed=True, consequences_checked=False
    )
    assert partial["may_say_fixed"] is False
    assert partial["cause_only"] is True


def test_sent_not_read_not_acceptance() -> None:
    assert may_treat_sent_as_read() is False
    assert may_treat_read_as_acceptance() is False


def test_fix_does_not_close_claim_or_refund() -> None:
    assert may_tech_fix_close_finance_claim() is False
    pay = build_confirmed_error_reply(
        ConfirmedErrorReplyKind.PAYMENT_IMPACT,
        facts={
            "false_pre_pay_promise": "о перерасчёте",
            "demand_text": "возврат",
            "demand_registered": True,
            "registration_ref_or_failure": "CLAIM-DEMO-1",
        },
    )
    assert "не заменяет рассмотрение" in pay["text"]
    assert "возврат выполнен" not in pay["text"].casefold()


def test_no_duplicate_claim_on_retry() -> None:
    assert may_create_duplicate_claim_on_retry() is False


def test_incomplete_uses_fallback_not_silence() -> None:
    facing = client_facing_error_reply(
        ConfirmedErrorReplyKind.GENERAL,
        facts={"wrong_fact": "x"},
    )
    assert facing["send"] is True
    assert facing["text"] == SAFE_INCOMPLETE_FACTS_FALLBACK
    assert facing["handoff_announced"] is False
    assert facing["claim_registered_announced"] is False
    assert "исправление завершено" in facing["text"].casefold()
    # формулировка отрицает завершение
    assert "не буду сообщать, что исправление завершено" in facing["text"].casefold()


def test_internal_labels_blocked_from_client() -> None:
    assert reply_has_banned_internal_labels("статус needs_recheck")
    facing = client_facing_error_reply(
        ConfirmedErrorReplyKind.GENERAL,
        facts={
            "wrong_fact": "дата",
            "confirmed_correction": "ok",
            "message_date": "01.01.2026",
            "what_done_or_limited": "needs_recheck применён",
            "next_step": "проверка",
        },
    )
    # внутренний ярлык в фактах → unsafe → fallback
    assert facing.get("fallback") is True or "needs_recheck" not in facing["text"]
