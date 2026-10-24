"""Сверка выписки ИЛС с трудовой книжкой (первичная проверка)."""

from __future__ import annotations

from typing import Any


def _emp(period: dict[str, Any]) -> str:
    return str(period.get("employer") or "").strip().casefold()


def _has_dates(period: dict[str, Any]) -> bool:
    return bool(period.get("date_from") or period.get("date_to"))


def compare_ils_vs_labor_book(
    ils_periods: list[dict], labor_periods: list[dict]
) -> list[dict]:
    """Вернуть список расхождений (даты, работодатели, пропуски).

    Не утверждает ошибку пенсии — только вопросы к проверке источников.
    """
    findings: list[dict[str, Any]] = []
    ils = [p for p in ils_periods if isinstance(p, dict)]
    labor = [p for p in labor_periods if isinstance(p, dict)]

    if not ils and labor:
        findings.append(
            {
                "type": "missing_in_ils",
                "detail": "Периоды есть в трудовой, в ИЛС не извлечены",
                "source_a": "labor_book",
                "source_b": "ils",
                "confidence": "medium",
                "next_action": "request_ils_or_detailed_review",
            }
        )
        return findings
    if ils and not labor:
        findings.append(
            {
                "type": "missing_in_labor",
                "detail": "Периоды есть в ИЛС, трудовой для сверки нет",
                "source_a": "ils",
                "source_b": "labor_book",
                "confidence": "medium",
                "next_action": "request_labor_book",
            }
        )
        return findings

    labor_emps = {_emp(p) for p in labor if _emp(p)}
    ils_emps = {_emp(p) for p in ils if _emp(p)}
    for emp in sorted(labor_emps - ils_emps):
        if not emp:
            continue
        findings.append(
            {
                "type": "missing_in_ils",
                "detail": f"Работодатель из трудовой не найден в ИЛС: {emp}",
                "period_ref": emp,
                "source_a": "labor_book",
                "source_b": "ils",
                "confidence": "low",
                "next_action": "detailed_review",
            }
        )
    for emp in sorted(ils_emps - labor_emps):
        if not emp:
            continue
        findings.append(
            {
                "type": "missing_in_labor",
                "detail": f"Работодатель из ИЛС не найден в трудовой: {emp}",
                "period_ref": emp,
                "source_a": "ils",
                "source_b": "labor_book",
                "confidence": "low",
                "next_action": "detailed_review",
            }
        )

    # Грубые пересечения внутри одного источника (кандидат на ручную проверку).
    for label, periods in (("ils", ils), ("labor_book", labor)):
        dated = [p for p in periods if _has_dates(p) and _emp(p)]
        for i, a in enumerate(dated):
            for b in dated[i + 1 :]:
                if _emp(a) != _emp(b):
                    continue
                af, at = str(a.get("date_from") or ""), str(a.get("date_to") or "9999")
                bf, bt = str(b.get("date_from") or ""), str(b.get("date_to") or "9999")
                if af and bf and af <= bt and bf <= at:
                    findings.append(
                        {
                            "type": "overlap_suspect",
                            "detail": f"Возможное пересечение периодов в {label}",
                            "period_ref": _emp(a),
                            "source_a": label,
                            "source_b": label,
                            "confidence": "low",
                            "next_action": "manual_review",
                        }
                    )
                    break
    return findings
