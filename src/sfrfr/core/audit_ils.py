"""Сверка выписки ИЛС с трудовой книжкой (заглушка под алгоритм аудита)."""


def compare_ils_vs_labor_book(ils_periods: list[dict], labor_periods: list[dict]) -> list[dict]:
    """Вернуть список расхождений (даты, работодатели, пропуски)."""
    findings: list[dict] = []
    if not ils_periods and labor_periods:
        findings.append({"type": "missing_in_ils", "detail": "Периоды есть в трудовой, нет в ИЛС"})
    if ils_periods and not labor_periods:
        findings.append({"type": "missing_labor_book", "detail": "Нет данных трудовой для сверки"})
    return findings
