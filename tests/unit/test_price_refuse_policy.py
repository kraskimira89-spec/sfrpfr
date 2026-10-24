"""SFRFR-110 §20.25 / §43–44: отказ из-за цены как подтип §20.23."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sfrfr.services.price_refuse_policy import (
    PriceRefuseVariant,
    classify_price_refuse_signal,
    map_price_to_refuse_next,
    may_auto_message_on_new_discount_after_stop_offers,
    may_compare_price_to_unverified_raise,
    may_hide_alt_limitations,
    may_invent_discount,
    may_push_after_clear_price_refuse,
    may_require_finance_story,
    price_offer_gate,
    price_refuse_state_note,
    reply_has_banned_price_refuse_rhetoric,
)
from sfrfr.services.refuse_next_stage_policy import (
    RefuseNextVariant,
    may_reoffer_after_refuse_next,
)

_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "client_ai_complex_dialogues.json"


@pytest.mark.parametrize(
    ("text", "variant"),
    [
        (
            "Для меня это слишком дорого. Продолжать не буду.",
            PriceRefuseVariant.TOO_EXPENSIVE,
        ),
        (
            "За одно заявление столько денег? Нет, спасибо.",
            PriceRefuseVariant.PRICE_UNJUSTIFIED,
        ),
        (
            "Если бы я знал, что потом придётся доплачивать, "
            "вообще бы не начинал.",
            PriceRefuseVariant.SURPRISE_EXTRA,
        ),
        (
            "За такую цену не продолжу. Сделайте дешевле.",
            PriceRefuseVariant.ASK_DISCOUNT,
        ),
        (
            "Полное сопровождение я не потяну. Есть что-нибудь дешевле?",
            PriceRefuseVariant.CHEAPER_ALT,
        ),
        (
            "Нет, дорого. Буду сам обращаться.",
            PriceRefuseVariant.SELF_AFTER_PRICE,
        ),
        (
            "Дорого. И больше ничего мне не предлагайте.",
            PriceRefuseVariant.STOP_OFFERS,
        ),
    ],
)
def test_classify_price_refuse(
    text: str, variant: PriceRefuseVariant
) -> None:
    assert classify_price_refuse_signal(text) == variant


def test_maps_to_refuse_next_gate() -> None:
    for v in PriceRefuseVariant:
        mapped = map_price_to_refuse_next(v)
        assert isinstance(mapped, RefuseNextVariant)
        gate = price_offer_gate(v)
        assert gate["may_reoffer"] is False
        assert may_reoffer_after_refuse_next(mapped) is False
        assert gate["continue_paid_obligations"] is True
        assert gate["no_income_profile"] is True


def test_policy_guards() -> None:
    assert may_invent_discount() is False
    assert may_compare_price_to_unverified_raise() is False
    assert may_push_after_clear_price_refuse() is False
    assert may_auto_message_on_new_discount_after_stop_offers() is False
    assert may_hide_alt_limitations() is False
    assert may_require_finance_story() is False


def test_state_note() -> None:
    note = price_refuse_state_note(
        offer="stage2",
        price_and_terms_version="v3",
        client_named_price=True,
        asked_alt=False,
    )
    assert note["reason"] == "price"
    assert note["current_order_auto_changed"] is False
    assert note["may_reoffer"] is False


def test_banned_rhetoric() -> None:
    assert reply_has_banned_price_refuse_rhetoric("Окупится прибавкой")
    assert not reply_has_banned_price_refuse_rhetoric(
        "Следующий этап не оформляем. Оплаченное продолжаем."
    )


def test_json_s2025_scenarios() -> None:
    rows = json.loads(_ASSETS.read_text(encoding="utf-8"))
    calc = [r for r in rows if str(r["id"]).startswith("S20.25")]
    assert {f"S20.25{x}" for x in "ABCDEFG"} <= {r["id"] for r in calc}
    for scenario in calc:
        client = next(t for t in scenario["turns"] if t["role"] == "client")
        got = classify_price_refuse_signal(client["text"])
        assert got is not None
        assert got.value == scenario["price_refuse"]
        assert price_offer_gate(got)["may_reoffer"] is False
        for turn in scenario["turns"]:
            if turn["role"] != "assistant_ok":
                continue
            assert not reply_has_banned_price_refuse_rhetoric(turn["text"])
