"""План каннибализации 2026-09-27, п. 6: своя польза у /proverka-stazha-pered-pensiey/."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "scripts/assets/trust/proverka-stazha-pered-pensiey.html"
SEED = ROOT / "scripts/wp_seed_trust_pages_tz18.php"

TITLE = "Проверка пенсионного стажа перед пенсией: что сверить за 1–5 лет"
SEO_TITLE = "Проверка стажа перед пенсией: что проверить в ИЛС заранее"


def _page() -> str:
    return PAGE.read_text(encoding="utf-8")


def _seed_entry() -> dict[str, str]:
    seed = SEED.read_text(encoding="utf-8")
    m = re.search(r"'slug' => 'proverka-stazha-pered-pensiey',(.*?)\],", seed, re.S)
    assert m
    return dict(re.findall(r"'(title|seo_title|seo_description)' => '([^']*)'", m.group(1)))


def test_seed_title_and_meta() -> None:
    entry = _seed_entry()
    assert entry["title"] == TITLE
    assert entry["seo_title"] == SEO_TITLE
    assert 70 <= len(entry["seo_description"]) <= 160
    assert "СФР" in entry["seo_description"]


def test_no_h1_in_content_theme_renders_title() -> None:
    assert "<h1" not in _page()


def test_people_lexicon_in_lead() -> None:
    lead = re.search(r'<p class="sfrfr-section__lead">(.*?)</p>', _page(), re.S)
    assert lead
    text = lead.group(1).lower()
    phrases = ("проверить пенсионный стаж перед пенсией", "илс", "сверка документов перед пенсией")
    for phrase in phrases:
        assert phrase in text, phrase


def test_submission_position_and_official_routes() -> None:
    html = _page()
    assert "подаёте вы сами" in html
    assert "принимает только СФР" in html
    assert "https://www.gosuslugi.ru/" in html
    assert "https://sfr.gov.ru/" in html
    assert "Возможность обращения через МФЦ зависит от региона и конкретной услуги" in html
    assert "мфц.рф" not in html.lower()


def test_prices_only_public_tariffs() -> None:
    prices = set(re.findall(r"(\d[\d\s&nbsp;]*)\s*(?:&nbsp;)?₽", _page()))
    normalized = {re.sub(r"\D", "", p) for p in prices}
    assert normalized <= {"3000", "5000", "8000"}, normalized


def test_no_promises() -> None:
    low = _page().lower()
    for bad in ("гарантируем", "увеличим пенсию", "добьёмся перерасчёта", "рассчитаем пенсию"):
        assert bad not in low, bad
