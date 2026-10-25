from datetime import date

from sfrfr.core.stazh_compare import compare_stazh
from sfrfr.core.stazh_parse import (
    format_ymd,
    parse_ils_rows,
    parse_workbook_periods,
    ymd_between,
)

WORKBOOK = """ТРУДОВАЯ КНИЖКА
№ Дата
приёма Дата
увольнения Работодатель Сведения о приёме-
увольнении Основание
1 01.02.1989 Северный районо Энской области
ДЮСШ Принята тренером-преподавателем Пр.№14 от 01.02.89
2 11.04.1997 Северный районо Энской области
ДЮСШ Присвоена первая категория. Пр. №17 от 28.04.97
3 04.10.1999 Северный районо Энской области
ДЮСШ Уволена по собственному желанию Пр. №68 п.2 от 04.10.99
4 09.10.1999 Южная средняя школа №2 Южная средняя школа № 2 переименована.
Принята учителем. Пр. №29-к от 09.10.99
6 06.10.14 Южная средняя школа №2 Уволена по инициативе работника
пункт 3 статья 77 ТК РФ. Пр. №57 от 01.10.14
7 20.10.2014 Район Крайнего Севера, город Энск муниципальное учреждение "Ромашка".
Принята инструктором. Пр. №153-к
8 30.08.2017 МБДОУ «Ромашка» Продолжает работать по настоящее время.
"""

ILS_HEAD = """Сведения о состоянии индивидуального лицевого счета застрахованного лица
до 2015 года X X 0.000 25 лет 8 мес.
7 дн. X X X
01.01.2015 -
31.12.2015 (I
квартал, II
квартал, III
квартал, IV
квартал)
867935.91 113759.99 0.000 0 лет 11 мес.
23 дн.
п.19 ч.1. ст.
30
0 лет 11 мес.
17 дн.
МУНИЦИПАЛЬНОЕ УЧРЕЖДЕНИЕ
"РОМАШКА"
п.6 ч.1 ст.320 лет 11 мес.
17 дн.
01.01.2016 - 31.12.2016 (год) 0.00 0.00 0 лет 0 мес. 0 дн. ООО "ПУСТО"
01.01.2016 - 31.12.2016 (I квартал, II квартал) 1000.00 160.00 1 г. 0 мес. 0 дн.
п.6 ч.1 ст.32 1 г. 0 мес. 0 дн. "РОМАШКА"
01.02.1989 - 04.10.1999 10 лет 8 мес. 4 дн. УПРАВЛЕНИЕ ОБРАЗОВАНИЯ СЕВЕРНОГО РАЙОНА
01.01.1998 - 04.10.1999 1 г. 9 мес. 4 дн.п.6 ч.1 ст.32 1 г. 9 мес. 4 дн. КОМИТЕТ ПО СПОРТУ
09.10.1999 - 31.12.2001 2 г. 2 мес. 23 дн.п.19 ч.1. ст. 30 2 г. 2 мес. 23 дн. ЮЖНАЯ ШКОЛА
"""
ILS_2002 = (
    "01.01.2002 - 06.10.2014 163710.2612 лет 6 мес. 27 дн. "
    "п.19 ч.1. ст. 3012 лет 6 мес. 9 дн. ЮЖНАЯ ШКОЛА\n"
)
ILS_TAIL = (
    "20.10.2014 - 31.12.2014 24861.07 0 лет 2 мес. 12 дн. п.19 ч.1. ст. 300 лет 2 мес. 12 дн. "
    "п.6 ч.1 ст.32 0 лет 2 мес. 12 дн. 3. Страховщиком является Фонд\n"
)
ILS = ILS_HEAD + ILS_2002 + ILS_TAIL
TODAY = date(2026, 10, 25)


def test_ymd_between_matches_ils_style() -> None:
    assert ymd_between(date(1989, 2, 1), date(1999, 10, 4)) == (10, 8, 4)
    assert ymd_between(date(1989, 2, 1), date(1997, 12, 31)) == (8, 11, 0)
    assert format_ymd((8, 11, 0)) == "8 лет 11 мес."
    assert format_ymd((1, 2, 3)) == "1 год 2 мес. 3 дн."
    assert format_ymd((22, 0, 5)) == "22 года 5 дн."


def test_parse_workbook_periods_main_jobs() -> None:
    periods = parse_workbook_periods(WORKBOOK, today=TODAY)
    assert [(p.start, p.end) for p in periods] == [
        (date(1989, 2, 1), date(1999, 10, 4)),
        (date(1999, 10, 9), date(2014, 10, 6)),
        (date(2014, 10, 20), None),
    ]
    assert periods[0].label == "Северный районо Энской области ДЮСШ"
    assert periods[1].label == "Южная средняя школа №2"
    assert periods[2].label == "«Ромашка»"
    assert [p.north for p in periods] == [False, False, True]


def test_parse_workbook_skips_electronic_record() -> None:
    szi_td = (
        "Сведения о трудовой деятельности, предоставляемые из информационных ресурсов "
        "Фонда пенсионного и социального страхования\n1 ООО \"ПОД ДОМОМ\". 030-004-031522 "
        "26.02.2020 ПРИЕМ\n5 31.03.2023 УВОЛЬНЕНИЕ"
    )
    assert parse_workbook_periods(szi_td, today=TODAY) == []


def test_parse_ils_rows_glued_amounts_and_codes() -> None:
    rows = parse_ils_rows(ILS)
    by_start = {(r.start, r.end): r for r in rows}
    first = by_start[(date(2015, 1, 1), date(2015, 12, 31))]
    assert first.total == (0, 11, 23)
    assert first.north == (0, 11, 17)
    glued = by_start[(date(2002, 1, 1), date(2014, 10, 6))]
    assert glued.total == (12, 6, 27)
    assert glued.north is None
    assert by_start[(date(1998, 1, 1), date(1999, 10, 4))].north == (1, 9, 4)
    assert by_start[(date(2016, 1, 1), date(2016, 12, 31))].total in {(0, 0, 0), (1, 0, 0)}


def test_compare_finds_partial_north_stazh() -> None:
    out = compare_stazh(WORKBOOK, ILS, today=TODAY)
    assert out["ran"] is True
    kinds = [d["kind"] for d in out["discrepancies"]]
    assert kinds == ["north_partial"]
    d = out["discrepancies"][0]
    assert d["period"] == "01.02.1989–04.10.1999"
    assert "01.02.1989–31.12.1997" in d["detail"]
    assert "8 лет 11 мес." in d["detail"]
    assert "только за 01.01.1998–04.10.1999" in d["detail"]
    assert "найдено расхождений: 1" in out["summary"]


def test_compare_flags_period_missing_in_ils() -> None:
    out = compare_stazh(WORKBOOK, ILS_HEAD + ILS_TAIL, today=TODAY)
    missing = [d for d in out["discrepancies"] if d["kind"] == "not_in_ils"]
    assert len(missing) == 1
    assert missing[0]["period"] == "09.10.1999–06.10.2014"
    assert "01.01.2002–06.10.2014" in missing[0]["detail"]


def test_compare_clean_when_ils_matches() -> None:
    ils = ILS.replace(
        "01.02.1989 - 04.10.1999 10 лет 8 мес. 4 дн.",
        "01.02.1989 - 04.10.1999 10 лет 8 мес. 4 дн. п.6 ч.1 ст.32 10 лет 8 мес. 4 дн.",
    )
    out = compare_stazh(WORKBOOK, ils, today=TODAY)
    assert out["ran"] is True
    assert out["discrepancies"] == []
    assert "расхождений" in out["summary"] and "не найдено" in out["summary"]


def test_compare_not_ran_without_rows() -> None:
    out = compare_stazh(WORKBOOK, "пустая выписка", today=TODAY)
    assert out["ran"] is False
    assert out["reason"]
