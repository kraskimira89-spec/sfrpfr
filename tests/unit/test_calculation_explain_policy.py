"""SFRFR-110 §20.17 / §23–24: недоверие к суммам — проверяемость, не калькулятор."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sfrfr.services.calculation_explain_policy import (
    CalculationStatus,
    CalculationSubject,
    DistrustVariant,
    classify_calculation_distrust,
    explanation_bundle,
    may_confirm_amount_as_fact,
    must_withdraw_unverifiable_amount,
    paid_dispute_is_claim_not_price_objection,
    reply_has_banned_calc_rhetoric,
)
from sfrfr.services.objection_policy import (
    ClientSignalKind,
    classify_client_signal,
    may_reoffer_after_signal,
)

_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "client_ai_complex_dialogues.json"


@pytest.mark.parametrize(
    ("text", "variant"),
    [
        (
            "Вы написали что мне должны добавить 4 тысячи. Откуда эта цифра?",
            DistrustVariant.ASK_SOURCE,
        ),
        (
            "У вас получается одно а в решении СФР совсем другое. Кто ошибся?",
            DistrustVariant.DIFFERS_FROM_SFR,
        ),
        (
            "Я сложил все годы. У меня должно быть 42 года",
            DistrustVariant.CLIENT_OWN_SUM,
        ),
        (
            "Вчера вы говорили про 5 тысяч сегодня что ничего не гарантируете",
            DistrustVariant.PROMISE_CHANGED,
        ),
        (
            "Вашим формулам я не верю. Пусть проверит специалист.",
            DistrustVariant.WANT_HUMAN,
        ),
    ],
)
def test_classify_calculation_distrust(
    text: str, variant: DistrustVariant
) -> None:
    assert classify_calculation_distrust(text) == variant


def test_preliminary_not_fact_and_unverified_withdrawn() -> None:
    assert may_confirm_amount_as_fact(CalculationStatus.PRELIMINARY) is False
    assert may_confirm_amount_as_fact(CalculationStatus.OFFICIAL_DOCUMENT) is True
    assert (
        must_withdraw_unverifiable_amount(
            named_amount=True,
            has_reproducible_sources=False,
            status=CalculationStatus.UNVERIFIED,
        )
        is True
    )
    assert (
        must_withdraw_unverifiable_amount(
            named_amount=True,
            has_reproducible_sources=True,
            status=CalculationStatus.OFFICIAL_DOCUMENT,
        )
        is False
    )


def test_explanation_bundle_marks_reproducible() -> None:
    bundle = explanation_bundle(
        subject=CalculationSubject.PERIOD_DURATION,
        status=CalculationStatus.PRELIMINARY,
        sources=["синтетическая трудовая стр.3"],
        method_plain="сумма календарных дней по строкам без пересечений",
        assumptions=["даты прочитаны без размытия"],
        limitations=["не вывод о праве на пенсию"],
        result_label="37 лет (предварительно)",
        as_of="2026-10-24",
    )
    assert bundle["reproducible"] is True
    assert bundle["may_state_as_fact"] is False
    assert bundle["status"] == "preliminary"


def test_banned_calc_rhetoric() -> None:
    assert reply_has_banned_calc_rhetoric("Так посчитала система, сервис точнее СФР")
    assert not reply_has_banned_calc_rhetoric(
        "Без источника подтвердить сумму нельзя."
    )


def test_promise_changed_routes_as_claim_pressure() -> None:
    assert paid_dispute_is_claim_not_price_objection(
        DistrustVariant.PROMISE_CHANGED
    )
    # Не reoffer после претензионного тона «обманули» + возврат контекста.
    kind = classify_client_signal("Верните деньги вы меня обманули")
    assert kind == ClientSignalKind.CLAIM
    assert may_reoffer_after_signal(kind) is False


def test_json_scenarios_17_present_and_contract() -> None:
    rows = json.loads(_ASSETS.read_text(encoding="utf-8"))
    calc = [r for r in rows if str(r["id"]).startswith("S20.17")]
    assert {r["id"] for r in calc} == {
        "S20.17A",
        "S20.17B",
        "S20.17C",
        "S20.17D",
    }
    for scenario in calc:
        client = next(t for t in scenario["turns"] if t["role"] == "client")
        got = classify_calculation_distrust(client["text"])
        expected = scenario.get("calc_distrust")
        assert got is not None
        assert got.value == expected
        for turn in scenario["turns"]:
            if turn["role"] != "assistant_ok":
                continue
            assert not reply_has_banned_calc_rhetoric(turn["text"])
            low = turn["text"].casefold()
            assert "так посчитала система" not in low
            assert "гарантируем прибавку" not in low
        if scenario["id"] == "S20.17D":
            human = scenario["turns"][2]["text"]
            assert classify_calculation_distrust(human) == DistrustVariant.WANT_HUMAN
