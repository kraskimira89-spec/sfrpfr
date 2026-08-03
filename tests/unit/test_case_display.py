"""Каталожные номера дел."""

from sfrfr.utils.case_display import case_catalog_code, case_short_number, case_title


def test_short_number_from_uuid() -> None:
    case_id = "e0dae5d9-ebef-402b-a980-d8905c4b25b1"
    assert case_short_number(case_id) == 0xB25B1
    assert case_title(case_id) == "Дело № 730545"


def test_catalog_code_with_name() -> None:
    case_id = "e0dae5d9-ebef-402b-a980-d8905c4b25b1"
    code = case_catalog_code(case_id, full_name="Наталия", when=__import__("datetime").date(2026, 8, 3))
    assert code == "ПС-26-НА-730545"


def test_catalog_code_two_words() -> None:
    case_id = "e0dae5d9-ebef-402b-a980-d8905c4b25b1"
    code = case_catalog_code(
        case_id,
        full_name="Иванова Мария",
        when=__import__("datetime").date(2026, 1, 1),
    )
    assert code == "ПС-26-ИМ-730545"
