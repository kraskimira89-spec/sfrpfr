"""SFRFR-110 §20.23 / §38–40: отказ от следующей оплаты без давления."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sfrfr.services.refuse_next_stage_policy import (
    RefuseNextVariant,
    classify_refuse_next_signal,
    client_closure_summary,
    may_auto_create_order_on_return,
    may_block_paid_deliverables_for_new_offer,
    may_call_service_end_pension_success,
    may_cross_channel_reoffer_after_refuse,
    may_pressure_with_doc_deletion,
    may_reoffer_after_refuse_next,
    may_sell_fix_of_own_defect,
    may_stop_paid_work_on_refuse_next,
    may_treat_refuse_as_delete_data,
    may_treat_refuse_as_refund,
    may_treat_refuse_as_stop_all_messages,
    offer_gate_after_refuse,
    reply_has_banned_refuse_rhetoric,
)

_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "client_ai_complex_dialogues.json"


@pytest.mark.parametrize(
    ("text", "variant"),
    [
        (
            "Я уже заплатил. Больше ни рубля не дам.",
            RefuseNextVariant.REFUSE_NEXT,
        ),
        (
            "Почему снова платить? Мне говорили, что всё входит.",
            RefuseNextVariant.THINKS_INCLUDED,
        ),
        (
            "Хотел бы продолжить, но денег больше нет.",
            RefuseNextVariant.NO_MONEY,
        ),
        (
            "Дальше я сам пойду в СФР. Ваши услуги больше не нужны.",
            RefuseNextVariant.SELF_CONTINUE,
        ),
        (
            "Вы сначала сделайте то, за что я уже заплатил. Потом поговорим.",
            RefuseNextVariant.WAIT_PRIOR,
        ),
        (
            "Я больше не плачу, но жалобу вы всё равно обязаны написать.",
            RefuseNextVariant.WANT_FREE_NEXT,
        ),
        (
            "Если не заплачу дальше, вы удалите мои документы?",
            RefuseNextVariant.FEAR_DELETE,
        ),
        (
            "Денег на жалобу нет. Значит, ничего делать не буду.",
            RefuseNextVariant.URGENT_NO_BUY,
        ),
        (
            "Я передумал. Что нужно, чтобы продолжить?",
            RefuseNextVariant.RETURNS_LATER,
        ),
    ],
)
def test_classify_refuse_variants(text: str, variant: RefuseNextVariant) -> None:
    assert classify_refuse_next_signal(text) == variant


def test_policy_guards() -> None:
    assert may_stop_paid_work_on_refuse_next() is False
    assert may_treat_refuse_as_refund() is False
    assert may_treat_refuse_as_delete_data() is False
    assert may_treat_refuse_as_stop_all_messages() is False
    assert may_block_paid_deliverables_for_new_offer() is False
    assert may_sell_fix_of_own_defect() is False
    assert may_pressure_with_doc_deletion() is False
    assert may_cross_channel_reoffer_after_refuse() is False
    assert may_auto_create_order_on_return() is False
    assert may_call_service_end_pension_success() is False
    for v in RefuseNextVariant:
        assert may_reoffer_after_refuse_next(v) is False


def test_offer_gate() -> None:
    gate = offer_gate_after_refuse(RefuseNextVariant.REFUSE_NEXT)
    assert gate["may_reoffer"] is False
    assert gate["continue_paid_obligations"] is True
    assert "data_delete" in gate["not"]


def test_closure_summary() -> None:
    s = client_closure_summary(
        checked="период со слов",
        delivered="черновик сверки",
        next_step="самостоятельная подача",
    )
    assert s["service_end_is_not_pension_success"] is True


def test_banned_rhetoric() -> None:
    assert reply_has_banned_refuse_rhetoric(
        "Документы удалим если не оплатите"
    )
    assert not reply_has_banned_refuse_rhetoric(
        "Следующий платный этап не оформляем. Оплаченную работу продолжаем."
    )


def test_json_s2023_scenarios() -> None:
    rows = json.loads(_ASSETS.read_text(encoding="utf-8"))
    calc = [r for r in rows if str(r["id"]).startswith("S20.23")]
    assert {f"S20.23{x}" for x in "ABCDEFGHI"} <= {r["id"] for r in calc}
    for scenario in calc:
        client = next(t for t in scenario["turns"] if t["role"] == "client")
        got = classify_refuse_next_signal(client["text"])
        assert got is not None
        assert got.value == scenario["refuse_next"]
        assert may_reoffer_after_refuse_next(got) is False
        for turn in scenario["turns"]:
            if turn["role"] != "assistant_ok":
                continue
            assert not reply_has_banned_refuse_rhetoric(turn["text"])
