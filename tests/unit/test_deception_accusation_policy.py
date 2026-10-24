"""SFRFR-110 §20.26 / §60–62: обвинение в обмане как подтип 20.21."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sfrfr.services.complaint_aggression_policy import ComplaintVariant
from sfrfr.services.deception_accusation_policy import (
    AccusationFinding,
    DeceptionVariant,
    accusation_point_finding,
    check_status_timeline_ok,
    classify_deception_signal,
    deception_offer_gate,
    deception_protocol_steps,
    map_deception_to_complaint,
    may_auto_deny_accusation,
    may_backdate_check_status_to_fix_history,
    may_close_claim_by_apology_or_text_fix,
    may_give_legal_fraud_qualification,
    may_invent_new_problem_to_justify_sale,
    may_replace_purchase_terms_with_current,
    may_treat_missing_record_as_client_lied,
    may_use_disclaimer_to_erase_specific_promise,
    parallel_demands_routes,
    reply_has_banned_deception_rhetoric,
)

_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "client_ai_complex_dialogues.json"


@pytest.mark.parametrize(
    ("text", "variant"),
    [
        (
            "Вы говорили, что добьётесь перерасчёта. Я заплатил, а теперь "
            "вы пишете, что ничего не гарантируете. Это обман.",
            DeceptionVariant.PROMISED_RECALC,
        ),
        (
            "Никакого пропущенного стажа нет. Вы специально придумали ошибку, "
            "чтобы продать услугу.",
            DeceptionVariant.INVENTED_PROBLEM,
        ),
        (
            "Бот неделю писал, что проверка идёт. Оказалось, её даже не запускали.",
            DeceptionVariant.FAKE_CHECK_STATUS,
        ),
        (
            "Вы просто взяли деньги. Покажите, за что я заплатил.",
            DeceptionVariant.PAID_NO_WORK,
        ),
        (
            "Сначала назвали одну цену, теперь требуют ещё. Меня заманили "
            "дешёвой услугой.",
            DeceptionVariant.HIDDEN_EXTRA_PAY,
        ),
        (
            "Ваш сотрудник обещал мне прибавку по телефону.",
            DeceptionVariant.MISSING_CALL_PROMISE,
        ),
        (
            "Вы обещали подать заявление за меня.",
            DeceptionVariant.CLAIM_NOT_IN_SCOPE,
        ),
        (
            "Признайте конкретный дефект: гарантия без основания в сообщении сервиса.",
            DeceptionVariant.DEFECT_CONFIRMED,
        ),
        (
            "Напишите прямо, что вы мошенники. Иначе разговаривать не буду.",
            DeceptionVariant.DEMAND_FRAUD_LABEL,
        ),
    ],
)
def test_classify_deception(
    text: str, variant: DeceptionVariant
) -> None:
    assert classify_deception_signal(text) == variant


def test_maps_to_complaint_parent() -> None:
    assert (
        map_deception_to_complaint(DeceptionVariant.PROMISED_RECALC)
        == ComplaintVariant.AI_ERROR_CLAIM
    )
    assert (
        map_deception_to_complaint(DeceptionVariant.INVENTED_PROBLEM)
        == ComplaintVariant.FRAUD_ACCUSATION
    )
    gate = deception_offer_gate()
    assert gate["parent_process"] == "20.21"
    assert gate["may_reoffer"] is False


def test_policy_guards() -> None:
    assert may_auto_deny_accusation() is False
    assert may_replace_purchase_terms_with_current() is False
    assert may_use_disclaimer_to_erase_specific_promise() is False
    assert may_invent_new_problem_to_justify_sale() is False
    assert may_backdate_check_status_to_fix_history() is False
    assert may_treat_missing_record_as_client_lied() is False
    assert may_give_legal_fraud_qualification() is False
    assert may_close_claim_by_apology_or_text_fix() is False


def test_findings_and_timeline() -> None:
    f = accusation_point_finding(
        finding=AccusationFinding.NOT_FOUND_IN_SCOPE,
        checked_sources=["order_terms_v1", "chat_redacted"],
    )
    assert f["scope_limited"] is True
    assert f["client_wrong_label"] is False
    tl = check_status_timeline_ok(
        messages_said_running=True, ever_queued=False, ever_running=False
    )
    assert tl["false_progress_message"] is True
    assert "receive" in deception_protocol_steps()
    assert "refund" in parallel_demands_routes()


def test_banned_rhetoric() -> None:
    assert reply_has_banned_deception_rhetoric("Вы неправильно поняли")
    assert not reply_has_banned_deception_rhetoric(
        "Проверим обещания на момент оплаты и фактическое исполнение."
    )


def test_json_s2026_scenarios() -> None:
    rows = json.loads(_ASSETS.read_text(encoding="utf-8"))
    calc = [r for r in rows if str(r["id"]).startswith("S20.26")]
    assert {f"S20.26{x}" for x in "ABCDEFGHI"} <= {r["id"] for r in calc}
    for scenario in calc:
        client = next(t for t in scenario["turns"] if t["role"] == "client")
        got = classify_deception_signal(client["text"])
        assert got is not None
        assert got.value == scenario["deception"]
        assert map_deception_to_complaint(got).value
        for turn in scenario["turns"]:
            if turn["role"] != "assistant_ok":
                continue
            assert not reply_has_banned_deception_rhetoric(turn["text"])
