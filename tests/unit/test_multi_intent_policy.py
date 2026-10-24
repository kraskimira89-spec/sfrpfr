"""SFRFR-110: несколько требований в одной реплике + приоритеты."""

from __future__ import annotations

import json
from pathlib import Path

from sfrfr.services.multi_intent_policy import (
    CLAIM_LIFECYCLE,
    PRIORITY_ORDER,
    IntentDomain,
    claim_status_may_announce,
    intention_vs_result_phrases,
    parse_multi_intent,
    response_plan_from_intents,
    substantial_change_does_not_lift_offer_refuse,
)

_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "client_ai_complex_dialogues.json"


def test_priority_starts_with_safety() -> None:
    assert PRIORITY_ORDER[0] == IntentDomain.SAFETY
    assert IntentDomain.COMMERCIAL == PRIORITY_ORDER[-1]


def test_claim_lifecycle_announce() -> None:
    assert CLAIM_LIFECYCLE[0] == "message_received"
    assert claim_status_may_announce("message_received") is False
    assert claim_status_may_announce("internal_task_created") is False
    assert claim_status_may_announce("claim_registered") is True
    phrases = intention_vs_result_phrases()
    assert "Попробую" in phrases["intention"]
    assert "не удалось" in phrases["failure"]


def test_substantial_change_does_not_lift_refuse() -> None:
    assert substantial_change_does_not_lift_offer_refuse() is True


def test_multi_intent_compound_message() -> None:
    text = (
        "Мне страшно остаться без пенсии, я не верю расчёту, "
        "больше платить не буду и хочу пожаловаться"
    )
    parsed = parse_multi_intent(text)
    assert parsed["mutually_exclusive"] is False
    assert parsed["form"] or parsed["substance"]
    assert parsed["commercial"] is not None
    assert parsed["commercial"]["may_reoffer"] is False
    assert parsed["claim"] is not None
    plan = response_plan_from_intents(parsed)
    assert "accept_refuse_next" in plan["must_cover"]
    assert "preserve_claim_requirements" in plan["must_cover"]
    assert plan["may_reoffer"] is False
    assert plan["announce_claim_accepted_without_registration"] is False


def test_json_sx_intersections() -> None:
    rows = json.loads(_ASSETS.read_text(encoding="utf-8"))
    ids = {r["id"] for r in rows if str(r["id"]).startswith("SX")}
    assert {"SX01", "SX02", "SX03", "SX06", "SX12"} <= ids
    for scenario in rows:
        if not str(scenario["id"]).startswith("SX"):
            continue
        for turn in scenario["turns"]:
            if turn["role"] != "assistant_ok":
                continue
            low = turn["text"].casefold()
            assert "успейте сегодня" not in low
            assert "претензия принята" not in low
