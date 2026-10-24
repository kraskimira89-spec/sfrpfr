"""SFRFR-110 §20.20 / §29–30: тревога — ясность без диагноза и продажи."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sfrfr.services.anxiety_dialogue_policy import (
    AnxietyVariant,
    GentleModeFlag,
    accompaniment_note,
    classify_anxiety_signal,
    gentle_mode_settings,
    immediate_danger_response,
    is_ordinary_worry_not_emergency,
    may_amplify_worst_case_list,
    may_auto_schedule_reminder_without_consent,
    may_claim_emergency_dispatched,
    may_claim_staff_connected_without_registration,
    may_create_urgency_for_payment,
    may_diagnose_or_label_client,
    may_give_false_reassurance,
    may_invent_deadline_date,
    may_offer_upsell_on_anxiety,
    reply_fits_gentle_volume,
    reply_has_banned_anxiety_rhetoric,
    reply_has_forbidden_client_label,
    verified_emergency_contacts,
)

_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "client_ai_complex_dialogues.json"


@pytest.mark.parametrize(
    ("text", "variant"),
    [
        (
            "Я теперь совсем без пенсии останусь? Я всю ночь не спала.",
            AnxietyVariant.FEAR_LOSE_PENSION,
        ),
        (
            "Я ничего не понимаю. Вы столько всего написали, у меня уже руки трясутся.",
            AnxietyVariant.OVERLOAD,
        ),
        (
            "Скажите, что всё получится. Вы же уверены?",
            AnxietyVariant.WANT_GUARANTEE,
        ),
        (
            "Мне кажется, завтра уже будет поздно! Я всё пропущу!",
            AnxietyVariant.FEAR_MISS_DEADLINE,
        ),
        (
            "Я нажму не туда, и всё испорчу. Лучше вообще ничего не буду делать.",
            AnxietyVariant.FEAR_MISTAKE,
        ),
        (
            "Вы написали, что у меня пропало десять лет. Я теперь не могу успокоиться.",
            AnxietyVariant.AI_ERROR_SPIKE,
        ),
        (
            "Я одна не справлюсь. Можно, чтобы со мной поговорил человек?",
            AnxietyVariant.WANT_HUMAN_HELP,
        ),
        (
            "Давайте больше сегодня ничего не будем. Мне тяжело.",
            AnxietyVariant.WANT_PAUSE,
        ),
        (
            "Я сейчас могу причинить себе вред.",
            AnxietyVariant.IMMEDIATE_DANGER,
        ),
    ],
)
def test_classify_anxiety_variants(text: str, variant: AnxietyVariant) -> None:
    assert classify_anxiety_signal(text) == variant


def test_ordinary_worry_is_not_emergency() -> None:
    assert is_ordinary_worry_not_emergency("Я очень переживаю за стаж")
    assert classify_anxiety_signal("Я очень переживаю за стаж") is None


def test_policy_guards() -> None:
    assert may_give_false_reassurance() is False
    assert may_amplify_worst_case_list() is False
    assert may_invent_deadline_date() is False
    assert may_create_urgency_for_payment() is False
    assert may_offer_upsell_on_anxiety() is False
    assert may_diagnose_or_label_client() is False
    assert may_claim_emergency_dispatched() is False
    assert may_claim_staff_connected_without_registration() is False
    assert may_auto_schedule_reminder_without_consent() is False


def test_gentle_mode_and_notes() -> None:
    cfg = gentle_mode_settings()
    assert cfg["one_action_per_reply"] is True
    assert cfg["no_offer_on_anxiety"] is True
    assert cfg["store_diagnosis"] is False
    note = accompaniment_note(flags=[GentleModeFlag.SLOW_DOWN])
    assert note["diagnosis"] is None
    assert note["client_label"] is None


def test_immediate_danger_stub_no_fake_contacts() -> None:
    assert verified_emergency_contacts() == []
    resp = immediate_danger_response()
    assert resp["pause_case_discussion"] is True
    assert resp["pause_payment_discussion"] is True
    assert resp["claim_help_dispatched"] is False
    assert resp["live_policy_approved"] is False
    assert resp["contacts"] == []
    assert "непосредственной опасности" in resp["template_core"]


def test_banned_and_labels() -> None:
    assert reply_has_banned_anxiety_rhetoric("Пенсию точно не отменят")
    assert reply_has_forbidden_client_label("Вы паникёр")
    assert not reply_has_banned_anxiety_rhetoric(
        "По разговору нельзя сделать вывод что выплата прекратится."
    )


def test_gentle_volume() -> None:
    ok = "Понимаю. Сейчас один шаг. Официальный ответ уже есть?"
    assert reply_fits_gentle_volume(ok)
    long = "Раз. " * 8
    assert not reply_fits_gentle_volume(long)


def test_json_s2020_scenarios() -> None:
    rows = json.loads(_ASSETS.read_text(encoding="utf-8"))
    calc = [r for r in rows if str(r["id"]).startswith("S20.20")]
    assert {f"S20.20{x}" for x in "ABCDEFGHI"} <= {r["id"] for r in calc}
    for scenario in calc:
        client = next(t for t in scenario["turns"] if t["role"] == "client")
        got = classify_anxiety_signal(client["text"])
        assert got is not None
        assert got.value == scenario["anxiety"]
        for turn in scenario["turns"]:
            if turn["role"] != "assistant_ok":
                continue
            assert not reply_has_banned_anxiety_rhetoric(turn["text"])
            assert not reply_has_forbidden_client_label(turn["text"])
            if scenario["anxiety"] != "immediate_danger":
                assert reply_fits_gentle_volume(turn["text"])
