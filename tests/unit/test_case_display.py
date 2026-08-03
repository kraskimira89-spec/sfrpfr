"""Каталожные номера дел."""

from datetime import date

from sfrfr.utils.case_display import case_catalog_code, case_short_number, case_title

CASE = "e0dae5d9-ebef-402b-a980-d8905c4b25b1"


def test_short_number_from_uuid() -> None:
    assert case_short_number(CASE) == 0xB25B1
    assert case_title(CASE) == "Дело ПС-730545"


def test_catalog_code_with_name() -> None:
    code = case_catalog_code(CASE, full_name="Наталия", when=date(2026, 8, 3))
    assert code == "ПС-26-НА-730545"


def test_catalog_code_two_words() -> None:
    code = case_catalog_code(CASE, full_name="Иванова Мария", when=date(2026, 1, 1))
    assert code == "ПС-26-ИМ-730545"
