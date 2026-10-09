"""Прогресс анкеты словами: «первый вопрос из четырёх вопросов»."""

from __future__ import annotations

import pytest

from sfrfr.utils.ru_question_progress import format_question_progress


@pytest.mark.parametrize(
    ("n", "total", "expected"),
    [
        (1, 4, "Первый вопрос из четырёх вопросов."),
        (2, 4, "Второй вопрос из четырёх вопросов."),
        (3, 4, "Третий вопрос из четырёх вопросов."),
        (4, 4, "Четвёртый вопрос из четырёх вопросов."),
        (5, 8, "Пятый вопрос из восьми вопросов."),
        (1, 1, "Первый вопрос из одного вопроса."),
        (2, 3, "Второй вопрос из трёх вопросов."),
    ],
)
def test_format_question_progress(n: int, total: int, expected: str) -> None:
    assert format_question_progress(n, total) == expected


def test_rejects_bad_range() -> None:
    with pytest.raises(ValueError):
        format_question_progress(0, 4)
    with pytest.raises(ValueError):
        format_question_progress(5, 4)
