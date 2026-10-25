"""Разбор текста трудовой книжки и выписки ИЛС на периоды (без LLM).

Длительности — как в ИЛС: календарная разница «лет / мес. / дн.»;
при сложении каждые 30 дней — месяц, каждые 12 месяцев — год.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta

Ymd = tuple[int, int, int]

_SZI_TD_RE = re.compile(r"(?i)сведения о трудовой деятельности,\s*предоставляемые")
_ENTRY_RE = re.compile(r"(?<![\d.№])(\d{1,3})\s+(\d{2})\.(\d{2})\.(\d{4}|\d{2})(?!\d)")
_HIRE_RE = re.compile(r"(?i)\b(?:приня[тв]\w*|назначен\w*|зачислен\w*)")
_DISMISS_RE = re.compile(
    r"(?i)\b(?:уволен\w*|освобожд\w* от должност\w*|"
    r"(?:трудовой\s+)?договор\w*\s+(?:прекращ|расторгн)\w*)"
)
_NORTH_RE = re.compile(r"(?i)крайнего\s+севера|приравненн\w*\s+к\s+района|\bРКС\b|\bМКС\b")
_QUOTED_RE = re.compile(r"[\"«“]([^\"»”]{2,60})[\"»”]")

_ILS_ROW_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})\s*-\s*(\d{2})\.(\d{2})\.(\d{4})")
_DUR = r"(\d{1,2})\s*(?:лет|года?|г\.)\s*(\d{1,2})\s*мес\.?\s*(\d{1,2})\s*дн"
# Код досрочного стажа + длительность: «п.6 ч.1 ст.32» склеивается с «0 лет» → «ст.320 лет».
_CODE_RE = re.compile(r"п\.\s*(\d{1,2})\s*ч\.\s*\d\.?\s*ст\.\s*(3[0-2])\s*" + _DUR)
# Общая длительность строки; сумма «163710.26» склеивается с «12 лет» → «.2612 лет».
_TOTAL_RE = re.compile(r"(?:(?<=\.\d{2})|(?<![\d.]))" + _DUR)
_NORTH_CODES = frozenset({"6", "7"})


@dataclass
class WorkPeriod:
    start: date
    end: date | None
    label: str
    north: bool = False


@dataclass
class IlsRow:
    start: date
    end: date
    total: Ymd | None
    north: Ymd | None


def _year(raw: str, today: date) -> int:
    if len(raw) == 4:
        return int(raw)
    yy = int(raw)
    return 2000 + yy if yy <= (today.year % 100) + 1 else 1900 + yy


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def ymd_between(start: date, end: date) -> Ymd:
    """Календарная длительность с start по end включительно."""
    excl = end + timedelta(days=1)
    y = excl.year - start.year
    m = excl.month - start.month
    d = excl.day - start.day
    if d < 0:
        m -= 1
        prev_month = excl.month - 1 or 12
        prev_year = excl.year if excl.month > 1 else excl.year - 1
        d += calendar.monthrange(prev_year, prev_month)[1]
    if m < 0:
        y -= 1
        m += 12
    return (y, m, d)


def sum_ymd(parts: list[Ymd]) -> Ymd:
    y = sum(p[0] for p in parts)
    m = sum(p[1] for p in parts)
    d = sum(p[2] for p in parts)
    m += d // 30
    d %= 30
    y += m // 12
    m %= 12
    return (y, m, d)


def ymd_days(value: Ymd) -> int:
    return value[0] * 365 + value[1] * 30 + value[2]


def _plural_years(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "год"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "года"
    return "лет"


def format_ymd(value: Ymd) -> str:
    y, m, d = value
    bits: list[str] = []
    if y:
        bits.append(f"{y} {_plural_years(y)}")
    if m:
        bits.append(f"{m} мес.")
    if d:
        bits.append(f"{d} дн.")
    return " ".join(bits) or "0 дн."


def fmt_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _label(text: str, keyword_at: int) -> str:
    quoted = _QUOTED_RE.search(text[:keyword_at])
    if quoted:
        return f"«{quoted.group(1).strip()}»"
    words: list[str] = []
    for word in text[:keyword_at].split():
        if word.lower() in {w.lower() for w in words}:
            break
        words.append(word)
        if len(words) >= 5:
            break
    return " ".join(words).strip(" ,.;")


def parse_workbook_periods(text: str, *, today: date) -> list[WorkPeriod]:
    """Основные места работы из бумажной трудовой (по записям приёма/увольнения)."""
    if not text or _SZI_TD_RE.search(text):
        return []
    flat = re.sub(r"\s+", " ", text)
    entries: list[tuple[date, str]] = []
    prev_no = 0
    matches = list(_ENTRY_RE.finditer(flat))
    for idx, m in enumerate(matches):
        no = int(m.group(1))
        if not prev_no < no <= prev_no + 3:
            continue
        when = _safe_date(_year(m.group(4), today), int(m.group(3)), int(m.group(2)))
        if when is None or when > today:
            continue
        nxt = next((x for x in matches[idx + 1 :] if no < int(x.group(1)) <= no + 3), None)
        body = flat[m.end() : nxt.start() if nxt else len(flat)].strip()
        entries.append((when, body))
        prev_no = no

    periods: list[WorkPeriod] = []
    cur: WorkPeriod | None = None
    for when, body in entries:
        dismiss = _DISMISS_RE.search(body)
        hire = None if dismiss else _HIRE_RE.search(body)
        if hire:
            if cur is not None:
                cur.end = when - timedelta(days=1)
                periods.append(cur)
            cur = WorkPeriod(
                start=when,
                end=None,
                label=_label(body, hire.start()),
                north=bool(_NORTH_RE.search(body)),
            )
        elif dismiss and cur is not None:
            cur.end = when
            cur.north = cur.north or bool(_NORTH_RE.search(body))
            periods.append(cur)
            cur = None
        elif cur is not None and _NORTH_RE.search(body):
            cur.north = True
    if cur is not None:
        periods.append(cur)
    return [p for p in periods if p.end is None or p.end >= p.start]


def parse_ils_rows(text: str) -> list[IlsRow]:
    """Строки выписки ИЛС «дд.мм.гггг - дд.мм.гггг» с длительностью и северным кодом."""
    flat = re.sub(r"\s+", " ", text or "")
    found = list(_ILS_ROW_RE.finditer(flat))
    rows: list[IlsRow] = []
    for idx, m in enumerate(found):
        start = _safe_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        end = _safe_date(int(m.group(6)), int(m.group(5)), int(m.group(4)))
        if start is None or end is None or end < start:
            continue
        seg_end = found[idx + 1].start() if idx + 1 < len(found) else min(len(flat), m.end() + 600)
        seg = flat[m.end() : seg_end]
        north: Ymd | None = None
        masked = seg
        for code in _CODE_RE.finditer(seg):
            dur = (int(code.group(3)), int(code.group(4)), int(code.group(5)))
            if code.group(2) == "32" and code.group(1) in _NORTH_CODES:
                north = dur if north is None or ymd_days(dur) > ymd_days(north) else north
            masked = masked.replace(code.group(0), " " * len(code.group(0)), 1)
        total_m = _TOTAL_RE.search(masked)
        total = (
            (int(total_m.group(1)), int(total_m.group(2)), int(total_m.group(3)))
            if total_m
            else None
        )
        if north is None and re.search(r"\b(?:РКС|МКС)\b", seg[:200]) and total:
            north = total
        rows.append(IlsRow(start=start, end=end, total=total, north=north))
    return rows
