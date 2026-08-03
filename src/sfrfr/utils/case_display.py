"""Человекочитаемые номера дел (каталог), UUID остаётся PK в БД."""

from __future__ import annotations

import re
from datetime import date


def case_short_number(case_id: str) -> int | None:
    """Стабильный короткий номер из последних 5 hex UUID (как в кабинете / MAX)."""
    hex_tail = re.sub(r"[^0-9a-fA-F]", "", case_id or "")[-5:]
    if len(hex_tail) < 5:
        return None
    try:
        n = int(hex_tail, 16)
    except ValueError:
        return None
    return n if n > 0 else None


def _initials(full_name: str | None) -> str:
    """1–2 буквы из ФИО для каталога (не полное ФИО)."""
    parts = [p for p in re.split(r"\s+", (full_name or "").strip()) if p]
    letters: list[str] = []
    if len(parts) >= 2:
        letters = [parts[0][0], parts[1][0]]
    elif len(parts) == 1:
        word = parts[0]
        letters = list(word[:2]) if len(word) >= 2 else [word[0], "Х"]
    else:
        return "ХХ"
    return "".join(letters).upper()


def case_catalog_code(
    case_id: str,
    *,
    full_name: str | None = None,
    when: date | None = None,
) -> str:
    """
    Каталожный код: ПС-{YY}-{ИИ}-{NNNNNN}

    Пример: ПС-26-НА-730545
    — ПС: Проверка стажа
    — YY: год заявки
    — ИИ: инициалы / первые буквы имени (удобно вести папки)
    — NNNNNN: короткий номер из UUID (совпадает с «Дело №» в кабинете)
    """
    n = case_short_number(case_id)
    if n is None:
        return "ПС-??-ХХ-000000"
    yy = f"{(when or date.today()).year % 100:02d}"
    return f"ПС-{yy}-{_initials(full_name)}-{n:06d}"


def case_title(case_id: str) -> str:
    """Заголовок для клиента: Дело ПС-730545."""
    n = case_short_number(case_id)
    if n is None:
        return "Дело ПС-—"
    return f"Дело ПС-{n}"
