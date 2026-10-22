"""Прогресс анкеты: «Вопрос N из 4.»"""

from __future__ import annotations

import pytest

from sfrfr.utils.ru_question_progress import format_question_progress, with_question_progress


@pytest.mark.parametrize(
    ("n", "total", "expected"),
    [
        (1, 4, "Вопрос 1 из 4."),
        (2, 4, "Вопрос 2 из 4."),
        (3, 4, "Вопрос 3 из 4."),
        (4, 4, "Вопрос 4 из 4."),
        (5, 8, "Вопрос 5 из 8."),
        (1, 1, "Вопрос 1 из 1."),
    ],
)
def test_format_question_progress(n: int, total: int, expected: str) -> None:
    assert format_question_progress(n, total) == expected


def test_with_question_progress_prefix() -> None:
    assert with_question_progress("Стаж?", n=2, total=4) == "Вопрос 2 из 4. Стаж?"


def test_rejects_bad_range() -> None:
    with pytest.raises(ValueError):
        format_question_progress(0, 4)
    with pytest.raises(ValueError):
        format_question_progress(5, 4)
