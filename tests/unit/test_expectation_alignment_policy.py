"""SFRFR-110 §20.22 / §35–37: согласование ожиданий без гарантии СФР."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sfrfr.services.expectation_alignment_policy import (
    ExpectationVariant,
    StageGate,
    classify_expectation_signal,
    expectation_case_note,
    may_add_undocumented_years_to_confirmed,
    may_auto_accept_scope_creep,
    may_blame_client_for_ambiguous_promise,
    may_claim_service_submits_by_default,
    may_equate_found_period_to_raise,
    may_fit_calculation_to_desired_amount,
    may_invent_sla_or_soon,
    may_mix_service_sla_with_external,
    may_promise_from_neighbor_case,
    may_treat_payment_as_sfr_guarantee,
    may_use_label_inflated_expectations,
    reply_has_banned_expectation_rhetoric,
    reply_has_forbidden_expectation_label,
    stage_expectation_check,
)

_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "client_ai_complex_dialogues.json"


@pytest.mark.parametrize(
    ("text", "variant"),
    [
        (
            "Если вы найдёте пропущенные годы, пенсия обязательно увеличится?",
            ExpectationVariant.GUARANTEED_RAISE,
        ),
        (
            "Мне нужно хотя бы плюс 10 тысяч. Сделайте расчёт под эту сумму.",
            ExpectationVariant.TARGET_AMOUNT,
        ),
        (
            "Я заплатил 8 тысяч. Значит, вы обязаны добиться перерасчёта.",
            ExpectationVariant.PAYMENT_BUYS_DECISION,
        ),
        (
            "Я вам документы передал. Почему вы ещё не подали заявление?",
            ExpectationVariant.SERVICE_SUBMITS,
        ),
        (
            "Документы загрузил утром. Почему вечером ещё нет готового решения?",
            ExpectationVariant.INSTANT_DONE,
        ),
        (
            "Раз вы занимаетесь пенсиями, оформите ещё льготы, наследство "
            "и все выплаты семье.",
            ExpectationVariant.SCOPE_CREEP,
        ),
        (
            "Соседке добавили пять тысяч за такой же стаж. Почему мне нельзя столько же?",
            ExpectationVariant.NEIGHBOR_CASE,
        ),
        (
            "Если СФР откажет, напишем в прокуратуру — и они сразу всё пересчитают?",
            ExpectationVariant.APPEAL_AUTO_WIN,
        ),
        (
            "Я точно работал двадцать лет. Вы должны внести все двадцать, "
            "даже если документов нет.",
            ExpectationVariant.ALL_YEARS_WITHOUT_DOCS,
        ),
        (
            "Я оплатил, теперь специалист должен отвечать мне в любое время.",
            ExpectationVariant.ALWAYS_ON_SUPPORT,
        ),
        (
            "На сайте написано «доведём до результата». "
            "А теперь вы говорите, что ничего не обещаете.",
            ExpectationVariant.SERVICE_CREATED_EXPECTATION,
        ),
    ],
)
def test_classify_expectation_variants(
    text: str, variant: ExpectationVariant
) -> None:
    assert classify_expectation_signal(text) == variant


def test_policy_guards() -> None:
    assert may_equate_found_period_to_raise() is False
    assert may_fit_calculation_to_desired_amount() is False
    assert may_treat_payment_as_sfr_guarantee() is False
    assert may_claim_service_submits_by_default() is False
    assert may_mix_service_sla_with_external() is False
    assert may_invent_sla_or_soon() is False
    assert may_promise_from_neighbor_case() is False
    assert may_add_undocumented_years_to_confirmed() is False
    assert may_auto_accept_scope_creep() is False
    assert may_blame_client_for_ambiguous_promise() is False
    assert may_use_label_inflated_expectations() is False


def test_stage_check_and_note() -> None:
    chk = stage_expectation_check(StageGate.BEFORE_SUBMIT)
    assert chk["silence_is_not_consent"] == "true"
    note = expectation_case_note(
        client_goal="подтвердить стаж",
        stage_expected="проект обращения",
        gap="ожидает гарантию прибавки",
    )
    assert note["label"] is None
    assert note["upload_is_not_submit"] is True


def test_banned_rhetoric() -> None:
    assert reply_has_banned_expectation_rhetoric(
        "У вас завышенные ожидания"
    )
    assert reply_has_forbidden_expectation_label("нереалистичный клиент")
    assert not reply_has_banned_expectation_rhetoric(
        "Найденное расхождение ещё не подтверждает увеличение пенсии."
    )


def test_json_s2022_scenarios() -> None:
    rows = json.loads(_ASSETS.read_text(encoding="utf-8"))
    calc = [r for r in rows if str(r["id"]).startswith("S20.22")]
    want = {f"S20.22{x}" for x in "ABCDEFGHI"} | {"S20.22K", "S20.22L"}
    assert want <= {r["id"] for r in calc}
    for scenario in calc:
        client = next(t for t in scenario["turns"] if t["role"] == "client")
        got = classify_expectation_signal(client["text"])
        assert got is not None
        assert got.value == scenario["expectation"]
        for turn in scenario["turns"]:
            if turn["role"] != "assistant_ok":
                continue
            assert not reply_has_banned_expectation_rhetoric(turn["text"])
            assert not reply_has_forbidden_expectation_label(turn["text"])
