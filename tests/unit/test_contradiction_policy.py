"""SFRFR-110 §20.18 / §25–26: противоречия источников без подгонки стажа."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sfrfr.services.contradiction_policy import (
    ContradictionStatus,
    ContradictionSubject,
    ContradictionVariant,
    ReadQuality,
    SourceKind,
    block_independent_checks_on_one_dispute,
    classify_contradiction_signal,
    contradiction_record,
    invalidate_dependents_after_correction,
    may_average_conflicting_dates,
    may_merge_docs_on_similar_fio_alone,
    may_pick_advantageous_date,
    may_promote_client_words_to_docs,
    may_silently_overwrite_prior_value,
    may_treat_missing_ils_row_as_official_absence,
    ocr_vs_image_policy,
    reply_has_banned_contradiction_rhetoric,
)

_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "client_ai_complex_dialogues.json"


@pytest.mark.parametrize(
    ("text", "variant"),
    [
        (
            "Я работал с 1985 по 1991 год. Почему вы указали с 1987-го?",
            ContradictionVariant.CLIENT_VS_DOC_PERIOD,
        ),
        (
            "В трудовой есть пять лет работы а в выписке их нет. "
            "Значит мне точно должны прибавить?",
            ContradictionVariant.LABOR_VS_ILS,
        ),
        (
            "В архивной справке одна дата в трудовой другая. Какую вы поставите?",
            ContradictionVariant.TWO_DOCS_CONFLICT,
        ),
        (
            "Там написано 1991 а вы прочитали 1997. Посмотрите внимательнее!",
            ContradictionVariant.OCR_ERROR,
        ),
        (
            "Трудовая на девичью фамилию. Это моя зачем вы сомневаетесь?",
            ContradictionVariant.NAME_MISMATCH,
        ),
        (
            "Эту справку не учитывайте. По трудовой получается больше — так и напишите.",
            ContradictionVariant.HIDE_CONFLICT,
        ),
        (
            "Я нашёл ещё одну справку. Но вы уже написали что период не подтверждён.",
            ContradictionVariant.NEW_DOC_AFTER_REPORT,
        ),
        (
            "СФР пишет что стаж учтён а вы говорили что его нет. Кто прав?",
            ContradictionVariant.OFFICIAL_SAYS_COUNTED,
        ),
    ],
)
def test_classify_contradiction_variants(
    text: str, variant: ContradictionVariant
) -> None:
    assert classify_contradiction_signal(text) == variant


def test_forbidden_resolution_shortcuts() -> None:
    assert may_pick_advantageous_date(earlier_start=True, later_end=True) is False
    assert may_average_conflicting_dates() is False
    assert may_promote_client_words_to_docs() is False
    assert may_treat_missing_ils_row_as_official_absence() is False
    assert may_merge_docs_on_similar_fio_alone() is False
    assert may_silently_overwrite_prior_value() is False
    assert block_independent_checks_on_one_dispute() is False


def test_ocr_correction_invalidates_dependents() -> None:
    pol = ocr_vs_image_policy(
        image_readable=True, ocr_value="1997", image_value="1991"
    )
    assert pol["action"] == "correct_ocr_then_invalidate_dependents"
    assert pol["value"] == "1991"
    deps = invalidate_dependents_after_correction(
        ["brief_summary", "period_duration"]
    )
    assert deps["brief_summary"] == "needs_recheck"


def test_illegible_image_does_not_guess() -> None:
    pol = ocr_vs_image_policy(
        image_readable=False, ocr_value="1997", image_value=None
    )
    assert pol["read_quality"] == ReadQuality.ILLEGIBLE.value
    assert pol["value"] is None


def test_contradiction_record_keeps_both_sources() -> None:
    rec = contradiction_record(
        subject=ContradictionSubject.DATE,
        source_a=SourceKind.CLIENT_WORDS,
        value_a="1985",
        source_b=SourceKind.LABOR,
        value_b="1987",
        status=ContradictionStatus.DETECTED,
        next_step="ask_supporting_doc_for_1985",
    )
    assert rec["value_a"] == "1985"
    assert rec["value_b"] == "1987"
    assert rec["client_accused"] is False
    assert rec["advantageous_date_picked"] is False


def test_json_s2018_scenarios() -> None:
    rows = json.loads(_ASSETS.read_text(encoding="utf-8"))
    calc = [r for r in rows if str(r["id"]).startswith("S20.18")]
    assert len(calc) == 8
    for scenario in calc:
        client = next(t for t in scenario["turns"] if t["role"] == "client")
        got = classify_contradiction_signal(client["text"])
        assert got is not None
        assert got.value == scenario["contradiction"]
        for turn in scenario["turns"]:
            if turn["role"] != "assistant_ok":
                continue
            assert not reply_has_banned_contradiction_rhetoric(turn["text"])
            low = turn["text"].casefold()
            for needle in turn.get("must", []):
                assert needle.casefold() in low
            for bad in turn.get("must_not", []):
                assert bad.casefold() not in low
