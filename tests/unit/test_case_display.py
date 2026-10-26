"""Каталожные и публичные номера дел."""

from datetime import date
from typing import Any

import pytest

from sfrfr.utils.case_display import (
    case_catalog_code,
    case_public_number,
    case_short_number,
    case_title,
)

CASE = "e0dae5d9-ebef-402b-a980-d8905c4b25b1"


def test_short_number_from_uuid() -> None:
    assert case_short_number(CASE) == 0xB25B1
    assert case_title(CASE) == "Дело ПС-730545"


def test_catalog_code_with_name() -> None:
    code = case_catalog_code(CASE, full_name="Наталия", when=date(2026, 8, 3))
    assert code == "ПС-26-НА-730545"


def test_catalog_code_two_words() -> None:
    code = case_catalog_code(CASE, full_name="Иванова Мария", when=date(2026, 1, 1))
    assert code == "ПС-26-ИМ-730545"


def test_public_number_case_yyyy_nnnnnn() -> None:
    assert case_public_number(CASE, when=date(2026, 10, 20)) == "CASE-2026-730545"
    assert case_public_number(CASE, when=date(2026, 1, 1)) == "CASE-2026-730545"


def test_public_number_stable_same_year_and_rejects_junk() -> None:
    a = case_public_number(CASE, when=date(2026, 5, 1))
    b = case_public_number(CASE, when=date(2026, 12, 31))
    assert a == b == "CASE-2026-730545"
    assert case_public_number("") is None
    assert case_public_number("not-a-uuid") is None


def test_public_number_concurrent_same_case_same_number() -> None:
    """Конкурентное «создание» одного UUID → один CASE-номер (derived, не seq)."""
    from concurrent.futures import ThreadPoolExecutor

    def once() -> str | None:
        return case_public_number(CASE, when=date(2026, 10, 22))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: once(), range(16)))
    assert set(results) == {"CASE-2026-730545"}


def test_public_number_repeat_does_not_change_existing() -> None:
    """Повтор запроса / «пересоздание» отображения — тот же номер, PK не трогаем."""
    first = case_public_number(CASE, when=date(2026, 10, 22))
    again = case_public_number(CASE, when=date(2026, 10, 22))
    assert first == again == "CASE-2026-730545"
    # NNNNNN стабилен при той же дате открытия; год берётся из when
    assert case_public_number(CASE, when=date(2026, 1, 1)) == first


def test_public_number_different_cases_different_nnnnnn() -> None:
    other = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    a = case_public_number(CASE, when=date(2026, 10, 22))
    b = case_public_number(other, when=date(2026, 10, 22))
    assert a != b
    assert a and b and a.startswith("CASE-2026-") and b.startswith("CASE-2026-")


def test_questionnaire_completed_text_includes_case_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sfrfr.integrations.max import questionnaire as q

    def _fixed_number(case_id: str | None, *, when: Any = None) -> str | None:
        return "CASE-2026-730545" if case_id == CASE else None

    monkeypatch.setattr(
        "sfrfr.utils.case_display.case_public_number",
        _fixed_number,
    )
    text = q.completed_text(CASE)
    assert "CASE-2026-730545" in text
    assert "Ваше дело CASE-2026-730545 создано" in text
    assert "ИЛС" in text
    assert "трудов" in text.lower()
    assert "перерасч" not in text.lower()
    assert "диагностик" not in text.lower()
    assert q.completed_text(None) == q.COMPLETED_TEXT
    assert q.completed_text("") == q.COMPLETED_TEXT
