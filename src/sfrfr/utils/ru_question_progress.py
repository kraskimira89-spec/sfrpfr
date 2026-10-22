"""Нумерация вопросов анкеты: «Вопрос N из 4.» (ТЗ-35 уточнение владельца)."""

from __future__ import annotations


def format_question_progress(n: int, total: int) -> str:
    """«Вопрос N из total.» — n и total с 1, total >= n."""
    if n < 1 or total < 1 or n > total:
        raise ValueError(f"bad progress: n={n}, total={total}")
    return f"Вопрос {n} из {total}."


def with_question_progress(body: str, *, n: int, total: int) -> str:
    """Префикс прогресса + текст вопроса."""
    prefix = format_question_progress(n, total)
    text = (body or "").strip()
    if not text:
        return prefix
    return f"{prefix} {text}"
