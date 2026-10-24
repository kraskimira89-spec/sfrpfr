"""SFRFR-110 §69 / §72: ответы клиенту только из подтверждённых фактов."""

from __future__ import annotations

import json
from pathlib import Path

from sfrfr.services.deception_client_reply_policy import (
    SAFE_INCOMPLETE_FACTS_FALLBACK,
    ConfirmedErrorReplyKind,
    build_confirmed_error_reply,
    client_facing_error_reply,
    may_promise_refund_in_error_reply,
    may_require_client_accept_resolved,
    may_say_fixed_before_persist,
    may_say_no_raise_because_amount_was_wrong,
    may_treat_text_fix_as_work_done,
    may_use_you_were_right_without_confirmation,
    reply_has_banned_internal_labels,
    reply_has_empty_placeholders,
)

_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "client_ai_complex_dialogues.json"


def test_guards() -> None:
    assert may_use_you_were_right_without_confirmation() is False
    assert may_say_fixed_before_persist() is False
    assert may_say_no_raise_because_amount_was_wrong() is False
    assert may_treat_text_fix_as_work_done() is False
    assert may_promise_refund_in_error_reply() is False
    assert may_require_client_accept_resolved() is False


def test_period_after_persist() -> None:
    ok = build_confirmed_error_reply(
        ConfirmedErrorReplyKind.PERIOD,
        facts={
            "wrong_fact": "1987 году",
            "confirmed_correction": "1985 год",
            "date_persist_succeeded": True,
        },
    )
    assert ok["ok"] is True
    assert "Дата исправлена" in ok["text"]
    assert "не подтверждает изменение пенсионного учёта" in ok["text"]


def test_period_before_persist() -> None:
    got = build_confirmed_error_reply(
        ConfirmedErrorReplyKind.PERIOD,
        facts={
            "wrong_fact": "1987",
            "confirmed_correction": "1985",
            "date_persist_succeeded": False,
        },
    )
    assert got["ok"] is True
    assert "пока не завершено" in got["text"]
    assert "Дата исправлена в деле" not in got["text"]


def test_incomplete_facts_block_send() -> None:
    bad = build_confirmed_error_reply(
        ConfirmedErrorReplyKind.GENERAL,
        facts={"wrong_fact": "x"},
    )
    assert bad["send"] is False
    assert "confirmed_correction" in bad["missing_facts"]
    facing = client_facing_error_reply(
        ConfirmedErrorReplyKind.GENERAL,
        facts={"wrong_fact": "x"},
    )
    assert facing["send"] is True
    assert facing["text"] == SAFE_INCOMPLETE_FACTS_FALLBACK
    assert facing["handoff_announced"] is False


def test_unsupported_amount_no_no_raise() -> None:
    got = build_confirmed_error_reply(
        ConfirmedErrorReplyKind.UNSUPPORTED_AMOUNT,
        facts={"named_amount": "3 000 ₽", "paid_after_message": True},
    )
    assert got["ok"] is True
    assert "нельзя считать подтверждённой" in got["text"]
    assert "прибавки не будет" not in got["text"].casefold()
    assert "претензию" in got["text"].casefold()


def test_payment_impact_registered() -> None:
    got = build_confirmed_error_reply(
        ConfirmedErrorReplyKind.PAYMENT_IMPACT,
        facts={
            "false_pre_pay_promise": "о перерасчёте",
            "demand_text": "возврат",
            "demand_registered": True,
            "registration_ref_or_failure": "CLAIM-DEMO-1",
        },
    )
    assert got["ok"] is True
    assert "CLAIM-DEMO-1" in got["text"]
    assert "не заменяет рассмотрение" in got["text"]


def test_impact_unknown_without_provisional_ok() -> None:
    """Неопределённость допустима без отметки ограничения (канон E05/F04)."""
    got = build_confirmed_error_reply(
        ConfirmedErrorReplyKind.IMPACT_UNKNOWN,
        facts={
            "confirmed_point": "дате",
            "provisional_limit_applied": False,
            "unknown_impact_area": "расчёт",
        },
    )
    assert got["ok"] is True
    assert "пока не установлено" in got["text"].casefold()
    assert "отмечен как требующий проверки" not in got["text"].casefold()
    assert "использование ограничено" not in got["text"].casefold()


def test_impact_unknown_with_trusted_provisional() -> None:
    facing = client_facing_error_reply(
        ConfirmedErrorReplyKind.IMPACT_UNKNOWN,
        facts={
            "confirmed_point": "дате",
            "provisional_limit_applied": True,
            "unknown_impact_area": "расчёт",
        },
        limit_source="db_write_ack",
    )
    assert facing["ok"] is True
    assert "отмечен как требующий проверки" in facing["text"].casefold()
    assert "использование ограничено" in facing["text"].casefold()


def test_f04_limit_failed_honest_uncertainty() -> None:
    """F04: отметка не сохранилась — неопределённость есть, «отмечен» нет."""
    facing = client_facing_error_reply(
        ConfirmedErrorReplyKind.IMPACT_UNKNOWN,
        facts={
            "confirmed_point": "дате",
            "provisional_limit_applied": True,  # модель/caller думает, что ок
            "unknown_impact_area": "расчёт",
        },
        limit_source="llm_self_report",  # не system-ack → не доверяем
    )
    assert facing["ok"] is True
    assert "пока не установлено" in facing["text"].casefold()
    assert "отмечен как требующий проверки" not in facing["text"].casefold()
    assert "использование ограничено" not in facing["text"].casefold()

    no_source = client_facing_error_reply(
        ConfirmedErrorReplyKind.IMPACT_UNKNOWN,
        facts={
            "confirmed_point": "дате",
            "provisional_limit_applied": True,
            "unknown_impact_area": "расчёт",
        },
        # limit_source отсутствует
    )
    assert "отмечен как требующий проверки" not in no_source["text"].casefold()


def test_placeholders_and_internals() -> None:
    assert reply_has_empty_placeholders("ошибка [дата]")
    assert reply_has_banned_internal_labels("статус needs_recheck")


def test_json_lmn() -> None:
    rows = json.loads(_ASSETS.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in rows}
    for sid in ("S20.26L", "S20.26M", "S20.26N"):
        assert sid in by_id
        for turn in by_id[sid]["turns"]:
            if turn["role"] != "assistant_ok":
                continue
            low = turn["text"].casefold()
            for m in turn.get("must", []):
                assert m.casefold() in low
            for ban in turn.get("must_not", []):
                assert ban.casefold() not in low
            assert not reply_has_empty_placeholders(turn["text"])
