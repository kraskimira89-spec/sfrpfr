"""Сверка периодов трудовой книжки с выпиской ИЛС (даты и северный стаж).

Только факты из двух документов: что есть в трудовой и чего нет в ИЛС.
Юридических выводов и сумм здесь нет.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sfrfr.core.stazh_parse import (
    IlsRow,
    WorkPeriod,
    Ymd,
    fmt_date,
    format_ymd,
    parse_ils_rows,
    parse_workbook_periods,
    sum_ymd,
    ymd_between,
    ymd_days,
)

Interval = tuple[date, date]

MIN_MISSING_DAYS = 30
MIN_FRAGMENT_DAYS = 7
MAX_DISCREPANCIES = 5
_DAY = timedelta(days=1)


def _days(iv: Interval) -> int:
    return (iv[1] - iv[0]).days + 1


def _merge(intervals: list[Interval]) -> list[Interval]:
    out: list[Interval] = []
    for start, end in sorted(intervals):
        if out and start <= out[-1][1] + _DAY:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def _subtract(base: Interval, covers: list[Interval]) -> list[Interval]:
    out: list[Interval] = []
    cur = base[0]
    for start, end in _merge(covers):
        if end < cur:
            continue
        if start > base[1]:
            break
        if start > cur:
            out.append((cur, min(start - _DAY, base[1])))
        cur = max(cur, end + _DAY)
        if cur > base[1]:
            return out
    if cur <= base[1]:
        out.append((cur, base[1]))
    return out


def _intersect(base: Interval, covers: list[Interval]) -> list[Interval]:
    out: list[Interval] = []
    for start, end in _merge(covers):
        lo, hi = max(start, base[0]), min(end, base[1])
        if lo <= hi:
            out.append((lo, hi))
    return out


def _significant(fragments: list[Interval]) -> list[Interval]:
    if sum(_days(f) for f in fragments) < MIN_MISSING_DAYS:
        return []
    return [f for f in fragments if _days(f) >= MIN_FRAGMENT_DAYS]


def _counts(row: IlsRow, duration: Ymd | None) -> bool:
    """Строка покрывает свои даты, если учтено не меньше половины её длины."""
    return duration is not None and ymd_days(duration) * 2 >= _days((row.start, row.end))


def _ranges(ivs: list[Interval]) -> str:
    return ", ".join(f"{fmt_date(s)}–{fmt_date(e)}" for s, e in ivs)


def _duration(ivs: list[Interval]) -> str:
    return format_ymd(sum_ymd([ymd_between(s, e) for s, e in ivs]))


def _period_short(p: WorkPeriod) -> str:
    return f"{fmt_date(p.start)}–{fmt_date(p.end)}" if p.end else f"с {fmt_date(p.start)}"


def _period_phrase(p: WorkPeriod) -> str:
    end = fmt_date(p.end) if p.end else "настоящее время"
    who = f"{p.label}, " if p.label else ""
    return f"{who}с {fmt_date(p.start)} по {end}"


def _is_year_edge(value: date) -> bool:
    return (value.month, value.day) in {(1, 1), (12, 31)}


def _north_hint(p: WorkPeriod, base: Interval, rows: list[IlsRow]) -> bool:
    """Северная местность: пометка в трудовой или северная строка ИЛС с той же датой границы."""
    if p.north:
        return True
    for row in rows:
        if row.north is None or not _intersect(base, [(row.start, row.end)]):
            continue
        if _days(_intersect(base, [(row.start, row.end)])[0]) < MIN_MISSING_DAYS:
            continue
        for ils_edge, book_edge in ((row.start, p.start), (row.end, p.end)):
            if book_edge is not None and ils_edge == book_edge and not _is_year_edge(ils_edge):
                return True
    return False


def _item(kind: str, title: str, detail: str, p: WorkPeriod, missing: list[Interval]) -> dict:
    return {
        "kind": kind,
        "title": title,
        "detail": detail,
        "period": _period_short(p),
        "missing": [[s.isoformat(), e.isoformat()] for s, e in missing],
        "missing_text": _duration(missing),
        "doc_type": "ils",
    }


def _not_in_ils(p: WorkPeriod, base: Interval, missing: list[Interval]) -> dict:
    whole = len(missing) == 1 and missing[0] == base
    title = (
        f"Период работы {_period_short(p)} не найден в выписке ИЛС"
        if whole
        else f"Часть периода работы {_period_short(p)} не отражена в выписке ИЛС"
    )
    detail = (
        f"По трудовой книжке: {_period_phrase(p)}. "
        f"В выписке ИЛС нет сведений за {_ranges(missing)} ({_duration(missing)})."
    )
    return _item("not_in_ils", title, detail, p, missing)


def _north(p: WorkPeriod, missing: list[Interval], covered: list[Interval]) -> dict:
    if covered:
        title = f"Северный стаж учтён не за весь период работы {_period_short(p)}"
        detail = (
            f"По трудовой книжке: {_period_phrase(p)}. "
            f"В выписке ИЛС северная отметка есть только за {_ranges(covered)}. "
            f"Без отметки — {_ranges(missing)} ({_duration(missing)})."
        )
        return _item("north_partial", title, detail, p, missing)
    title = f"Северный стаж за {_period_short(p)} в выписке ИЛС не отмечен"
    detail = (
        f"По трудовой книжке: {_period_phrase(p)} — район Крайнего Севера "
        f"или приравненная местность. В выписке ИЛС северной отметки за "
        f"{_ranges(missing)} нет ({_duration(missing)})."
    )
    return _item("north_missing", title, detail, p, missing)


def _places(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} место работы"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} места работы"
    return f"{n} мест работы"


def _not_ran(reason: str) -> dict[str, Any]:
    return {"ran": False, "reason": reason, "discrepancies": [], "summary": reason}


def compare_stazh(
    workbook_text: str, ils_text: str, *, today: date | None = None
) -> dict[str, Any]:
    """Расхождения трудовой книжки с выпиской ИЛС: пропущенные периоды и северная отметка."""
    today = today or date.today()
    rows = parse_ils_rows(ils_text)
    if not rows:
        return _not_ran("В выписке ИЛС не нашли строк с периодами — сверка не проводилась.")
    periods = parse_workbook_periods(workbook_text, today=today)
    if not periods:
        return _not_ran(
            "В трудовой книжке не нашли записей о приёме и увольнении — сверка не проводилась."
        )
    win_from = min(r.start for r in rows)
    win_to = max(r.end for r in rows)
    covered = [(r.start, r.end) for r in rows if _counts(r, r.total)]
    north_cov = [(r.start, r.end) for r in rows if _counts(r, r.north)]

    found: list[dict[str, Any]] = []
    for p in periods:
        base = (max(p.start, win_from), min(p.end or today, win_to))
        if base[1] < base[0]:
            continue
        missing = _significant(_subtract(base, covered))
        if missing:
            found.append(_not_in_ils(p, base, missing))
        if _north_hint(p, base, rows):
            no_north = _significant(_subtract(base, north_cov + missing))
            if no_north:
                found.append(_north(p, no_north, _intersect(base, north_cov)))

    found = found[:MAX_DISCREPANCIES]
    window = f"{fmt_date(win_from)}–{fmt_date(win_to)}"
    head = f"Сверили трудовую книжку ({_places(len(periods))}) с выпиской ИЛС за {window}: "
    summary = head + (
        f"найдено расхождений: {len(found)}."
        if found
        else "расхождений по датам и северному стажу не найдено."
    )
    return {
        "ran": True,
        "periods_checked": len(periods),
        "ils_rows": len(rows),
        "window": window,
        "discrepancies": found,
        "summary": summary,
    }
