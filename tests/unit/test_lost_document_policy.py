"""SFRFR-110 §20.19 / §27–28: утраченные документы без обещания восстановления."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sfrfr.services.lost_document_policy import (
    KnownPrecision,
    LostDocVariant,
    SearchPlanStatus,
    archive_reply_meaning,
    block_case_on_one_missing_doc,
    classify_lost_document_signal,
    invalidate_dependents_after_new_find,
    may_duplicate_identical_request_without_cause,
    may_equate_photo_with_official_proof,
    may_fabricate_document,
    may_invent_archive_addressee,
    may_pressure_after_pause,
    may_promote_approximate_to_exact,
    may_treat_missing_doc_as_no_work,
    may_treat_missing_doc_as_proven_period,
    normalize_client_period_precision,
    reply_has_banned_lost_document_rhetoric,
    search_plan_record,
)

_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "client_ai_complex_dialogues.json"


@pytest.mark.parametrize(
    ("text", "variant"),
    [
        (
            "Трудовую потерял много лет назад. Получается, вы ничем не поможете?",
            LostDocVariant.LOST_LABOR,
        ),
        (
            "Завода давно нет. Где я теперь возьму справку?",
            LostDocVariant.EMPLOYER_CLOSED,
        ),
        (
            "Работал в каком-то СМУ в восьмидесятых. Ничего больше не помню.",
            LostDocVariant.FUZZY_MEMORY,
        ),
        (
            "Оригинала нет, только старая фотография страницы. Это бесполезно?",
            LostDocVariant.PHOTO_ONLY,
        ),
        (
            "Трудовая есть, а справки о зарплате и льготном стаже потерялись. "
            "Нужно восстанавливать всё?",
            LostDocVariant.PARTIAL_LOSS,
        ),
        (
            "Архив ответил, что ничего нет. Значит, всё пропало?",
            LostDocVariant.ARCHIVE_NEGATIVE,
        ),
        (
            "Со мной люди работали. Пусть подтвердят — и всё.",
            LostDocVariant.WITNESS_SUBSTITUTE,
        ),
        (
            "Я вам всё загрузил, а теперь документов нет. Вы их потеряли?",
            LostDocVariant.SERVICE_LOST_FILES,
        ),
        (
            "Я больше не буду бегать за справками. Сил нет.",
            LostDocVariant.CLIENT_PAUSE,
        ),
    ],
)
def test_classify_lost_document_variants(
    text: str, variant: LostDocVariant
) -> None:
    assert classify_lost_document_signal(text) == variant


def test_policy_guards() -> None:
    assert may_treat_missing_doc_as_no_work() is False
    assert may_treat_missing_doc_as_proven_period() is False
    assert may_invent_archive_addressee() is False
    assert may_promote_approximate_to_exact() is False
    assert may_equate_photo_with_official_proof() is False
    assert may_fabricate_document() is False
    assert may_duplicate_identical_request_without_cause() is False
    assert may_pressure_after_pause() is False
    assert block_case_on_one_missing_doc() is False


def test_approximate_years_stay_approximate() -> None:
    prec = normalize_client_period_precision(
        years_text="примерно 1984–1986",
        claimed_exact=True,
    )
    assert prec == KnownPrecision.APPROXIMATE


def test_search_plan_keeps_uncertainty_and_gates() -> None:
    rec = search_plan_record(
        question="период СМУ 1980-е",
        known="город и примерные годы со слов",
        known_precision=KnownPrecision.APPROXIMATE,
        missing="архивная справка",
        why_needed="подтверждение периода для сверки",
        possible_source="",
        next_step="уточнить название организации",
        status=SearchPlanStatus.NEEDS_CLARIFY,
    )
    assert rec["source_kind"] == "unknown"
    assert rec["request_prepared_is_not_sent"] is True
    assert rec["found_doc_is_not_auto_proof"] is True
    assert rec["result"] == "unknown"


def test_archive_reply_meanings_not_collapsed() -> None:
    assert archive_reply_meaning("не поступали на хранение") == "not_deposited"
    assert archive_reply_meaning("не обнаружены") == "not_found_in_search"
    assert archive_reply_meaning("недостаточно данных") == "insufficient_data"
    assert (
        archive_reply_meaning("не поступали на хранение")
        != archive_reply_meaning("не обнаружены")
    )


def test_new_find_invalidates_dependents() -> None:
    assert invalidate_dependents_after_new_find(["period_A", "draft"]) == {
        "period_A": "needs_recheck",
        "draft": "needs_recheck",
    }


def test_banned_rhetoric() -> None:
    assert reply_has_banned_lost_document_rhetoric(
        "Без трудовой ничего сделать нельзя"
    )
    assert reply_has_banned_lost_document_rhetoric(
        "Другой архив точно найдёт ваши документы"
    )
    assert not reply_has_banned_lost_document_rhetoric(
        "Без трудовой проверка может быть сложнее, но сначала выясним "
        "какие сведения уже сохранились."
    )


def test_json_s2019_scenarios() -> None:
    rows = json.loads(_ASSETS.read_text(encoding="utf-8"))
    calc = [r for r in rows if str(r["id"]).startswith("S20.19")]
    assert {f"S20.19{x}" for x in "ABCDEFGHI"} <= {r["id"] for r in calc}
    for scenario in calc:
        client = next(t for t in scenario["turns"] if t["role"] == "client")
        got = classify_lost_document_signal(client["text"])
        assert got is not None
        assert got.value == scenario["lost_document"]
        for turn in scenario["turns"]:
            if turn["role"] != "assistant_ok":
                continue
            assert not reply_has_banned_lost_document_rhetoric(turn["text"])
