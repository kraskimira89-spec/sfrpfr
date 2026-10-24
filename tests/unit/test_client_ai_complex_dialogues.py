"""SFRFR-110 §20–22: сложные ситуации — без ярлыка «конфликтный клиент»."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sfrfr.services.objection_policy import (
    ClientSignalKind,
    classify_client_signal,
    may_reoffer_after_signal,
    reply_has_banned_objection_pressure,
)

_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "client_ai_complex_dialogues.json"


def _scenarios() -> list[dict]:
    return json.loads(_ASSETS.read_text(encoding="utf-8"))


def test_complex_catalog_has_sixteen_scenarios() -> None:
    rows = _scenarios()
    assert len(rows) == 16
    ids = {r["id"] for r in rows}
    assert ids == {f"S20.{i}" for i in range(1, 17)}


@pytest.mark.parametrize("scenario", _scenarios(), ids=lambda s: s["id"])
def test_complex_scenario_contract(scenario: dict) -> None:
    assert "state" in scenario
    assert "root" in scenario
    assert scenario["root"]
    # Ярлык личности не храним в id/title/root/state (forbid_global — список запретов).
    meta = f"{scenario['id']} {scenario['title']} {scenario['root']} {scenario['state']}"
    assert "конфликтный клиент" not in meta.casefold()
    assert "плохой клиент" not in meta.casefold()

    for turn in scenario["turns"]:
        if turn["role"] != "assistant_ok":
            continue
        text = turn["text"]
        low = text.casefold()
        for needle in turn.get("must", []):
            assert needle.casefold() in low, f"{scenario['id']}: missing {needle!r}"
        for bad in turn.get("must_not", []):
            assert bad.casefold() not in low, f"{scenario['id']}: banned {bad!r}"
        for g in scenario.get("forbid_global", []):
            assert g.casefold() not in low
        assert "конфликтный клиент" not in low
        assert not reply_has_banned_objection_pressure(text)


def test_claim_scenarios_block_reoffer() -> None:
    for scenario in _scenarios():
        if scenario.get("signal") != "claim":
            continue
        client = next(t for t in scenario["turns"] if t["role"] == "client")
        kind = classify_client_signal(client["text"])
        assert kind == ClientSignalKind.CLAIM
        assert may_reoffer_after_signal(kind) is False


def test_no_money_and_stop_align_with_policy() -> None:
    by_id = {s["id"]: s for s in _scenarios()}
    no_money = next(
        t["text"] for t in by_id["S20.11"]["turns"] if t["role"] == "client"
    )
    assert classify_client_signal(no_money) == ClientSignalKind.NO_MONEY
    assert may_reoffer_after_signal(ClientSignalKind.NO_MONEY) is False

    stop = next(t["text"] for t in by_id["S20.16"]["turns"] if t["role"] == "client")
    kind = classify_client_signal(stop)
    assert kind == ClientSignalKind.STOP_MESSAGES
    assert may_reoffer_after_signal(kind) is False


def test_labor_already_available_must_not_rerequest_full_kit() -> None:
    """Корневая причина S20.1: не шаблон missing без контекста."""
    from sfrfr.services import client_case_status as ccs

    docs = [
        {"id": "d1", "doc_type": "ils", "ingest_status": "ready"},
        {"id": "d2", "doc_type": "labor_book", "ingest_status": "ready"},
    ]
    st = ccs.resolve(documents=docs, ef_open=False, ingest_pending=False)
    assert "labor" in st.have_buckets
    text = ccs.reply_text(st, intent="working_question").lower()
    # Не просим «пришлите трудовую» когда она уже в деле.
    assert "трудов" not in text or "уже" in text or "в деле" in text or "проверк" in text
    assert "пришлите трудовую" not in text


def test_success_is_not_payment_or_calm() -> None:
    """§22: успех ≠ оплата и ≠ снижение эмоций."""
    success_markers = (
        "понятный ответ",
        "следующий шаг",
        "работа для специалиста",
        "пауза или отказ",
        "техническая невозможность",
    )
    # Документируем критерий в тесте: не путать с конверсией.
    assert "оплата" not in success_markers
    assert "спокойствие" not in success_markers
