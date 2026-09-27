"""График работы на /kontakty/ и адрес без квартиры в JSON-LD LocalBusiness."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KONTAKTY = ROOT / "scripts/assets/trust/kontakty.html"
SEO_META = ROOT / "scripts/wp-mu-plugins/sfrfr-seo-meta.php"
FOOTER = ROOT / "scripts/wp-mu-plugins/sfrfr-site-footer.php"

HOURS = "График работы: Пн–Пт 09:00–18:00 (UTC+5, 07:00–16:00 МСК)"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_kontakty_has_working_hours_in_contacts_block() -> None:
    html = _read(KONTAKTY)
    block = re.search(r"<h2>Связь</h2>\s*<p class=\"sfrfr-req\">(.*?)</p>", html, re.S)
    assert block, "блок «Связь» не найден"
    assert HOURS in block.group(1)


def test_local_business_street_address_without_apartment() -> None:
    php = _read(SEO_META)
    assert "'streetAddress' => 'ул. Рабочая, д. 109Б'," in php
    assert "кв. 4" not in php
    for field in (
        "'addressLocality' => 'Ноябрьск'",
        "'addressRegion' => 'ЯНАО'",
        "'postalCode' => '629804'",
    ):
        assert field in php


def test_legal_address_in_visible_requisites_kept() -> None:
    assert "д.&nbsp;109Б, кв.&nbsp;4" in _read(KONTAKTY)
    assert "д.&nbsp;109Б, кв.&nbsp;4" in _read(FOOTER)
