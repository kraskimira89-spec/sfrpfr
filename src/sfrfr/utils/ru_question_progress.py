"""Нумерация вопросов анкеты словами (для TTS и читаемости в чате)."""

from __future__ import annotations

_ORDINALS: dict[int, str] = {
    1: "Первый",
    2: "Второй",
    3: "Третий",
    4: "Четвёртый",
    5: "Пятый",
    6: "Шестой",
    7: "Седьмой",
    8: "Восьмой",
    9: "Девятый",
    10: "Десятый",
    11: "Одиннадцатый",
    12: "Двенадцатый",
    13: "Тринадцатый",
    14: "Четырнадцатый",
    15: "Пятнадцатый",
    16: "Шестнадцатый",
    17: "Семнадцатый",
    18: "Восемнадцатый",
    19: "Девятнадцатый",
    20: "Двадцатый",
}

_TOTAL_GENITIVE: dict[int, str] = {
    1: "одного",
    2: "двух",
    3: "трёх",
    4: "четырёх",
    5: "пяти",
    6: "шести",
    7: "семи",
    8: "восьми",
    9: "девяти",
    10: "десяти",
    11: "одиннадцати",
    12: "двенадцати",
    13: "тринадцати",
    14: "четырнадцати",
    15: "пятнадцати",
    16: "шестнадцати",
    17: "семнадцати",
    18: "восемнадцати",
    19: "девятнадцати",
    20: "двадцати",
}


def _questions_noun(total: int) -> str:
    """Существительное после «из N …»."""
    if total == 1:
        return "вопроса"
    return "вопросов"


def format_question_progress(n: int, total: int) -> str:
    """«Первый вопрос из четырёх вопросов.» — n и total с 1, total >= n."""
    if n < 1 or total < 1 or n > total:
        raise ValueError(f"bad progress: n={n}, total={total}")
    if n not in _ORDINALS or total not in _TOTAL_GENITIVE:
        # Запасной вариант для длинных опросов без прописи.
        return f"Вопрос {n} из {total}."
    return f"{_ORDINALS[n]} вопрос из {_TOTAL_GENITIVE[total]} {_questions_noun(total)}."


def with_question_progress(body: str, *, n: int, total: int) -> str:
    """Префикс прогресса + текст вопроса."""
    prefix = format_question_progress(n, total)
    text = (body or "").strip()
    if not text:
        return prefix
    return f"{prefix} {text}"
