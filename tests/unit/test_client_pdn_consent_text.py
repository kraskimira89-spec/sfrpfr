"""Экран согласия ПДн в MAX (ТЗ-35 §5, PR A1): реквизиты оператора, цели, срок, отзыв."""

from sfrfr.db.case_repository import CURRENT_CONSENT_VERSION
from sfrfr.services.client_pdn_consent import CONSENT_GATE_TEXT


def test_consent_gate_has_operator_requisites() -> None:
    for part in (
        "ООО «ПОД ПРИСМОТРОМ»",
        "ИНН 8905066468",
        "ОГРН 1208900000572",
        "629804",
        "г. Ноябрьск, ул. Рабочая, д. 109Б, кв. 4",
        "prismotr89@yandex.ru",
        "Лопакова Н. Ф.",
    ):
        assert part in CONSENT_GATE_TEXT, part


def test_consent_gate_has_purposes_term_revocation_and_links() -> None:
    text = CONSENT_GATE_TEXT.lower()
    for part in ("цели", "данные", "храним", "5 лет", "отозвать", "россии"):
        assert part in text, part
    assert "https://proverkastaza.ru/soglasie/" in CONSENT_GATE_TEXT
    assert "https://proverkastaza.ru/politika-pdn/" in CONSENT_GATE_TEXT
    assert "https://proverkastaza.ru/cookies/" in CONSENT_GATE_TEXT
    assert CURRENT_CONSENT_VERSION in CONSENT_GATE_TEXT
    assert "«Начать»" in CONSENT_GATE_TEXT


def test_consent_gate_has_no_bank_details_and_fits_max() -> None:
    for banned in ("40702810", "БИК", "р/с", "расчётный счёт"):
        assert banned not in CONSENT_GATE_TEXT
    assert len(CONSENT_GATE_TEXT) < 4000
