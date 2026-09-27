"""Доработка страниц P1 из seo-low-quality-recommendations-2026-09-27."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLOG_SEED = ROOT / "scripts/wp_seed_blog_tz11.php"
TRUST_SEED = ROOT / "scripts/wp_seed_trust_pages_tz18.php"
SEO_META = ROOT / "scripts/wp-mu-plugins/sfrfr-seo-meta.php"

ILS = {
    "file": ROOT / "scripts/assets/blog/21-zakazat-vypisku-ils.html",
    "slug": "kak-zakazat-vypisku-ils",
    "title": "Как получить выписку ИЛС через Госуслуги и что в ней проверить",
    "seo_title": "Выписка ИЛС на Госуслугах: как получить и чем отличается от СТД-Р",
    "must": ("выписка ИЛС", "Госуслуг", "СТД-Р", "СТД-СФР", "/ne-uchli-stazh/"),
}
LGOT = {
    "file": ROOT / "scripts/assets/blog/19-lgotnyy-stazh.html",
    "slug": "lgotnyy-i-pedagogicheskiy-stazh",
    "title": "Льготный стаж: какие документы подтверждают периоды и что делать, если не учли",
    "seo_title": "Льготный стаж не учли: документы для вредного и педагогического стажа",
    "must": (
        "<table",
        "Вредный стаж не учли",
        "Педагогический стаж не учли",
        "/arhivnaya-spravka-stazh/",
        "/otkaz-sfr/",
    ),
}
RELATIVE = {
    "file": ROOT / "scripts/assets/trust/pomoch-rodstvenniku-proverit-stazh.html",
    "slug": "pomoch-rodstvenniku-proverit-stazh",
    "title": "Как помочь родителям проверить стаж для пенсии: пошагово для родственников",
    "seo_title": "Помочь родственнику проверить стаж: доверенность, выписка ИЛС, шаги",
    "must": ("доверенност", "Госуслуг", "выписк", "/chek-list-dokumentov/", "<details"),
}
PAGES = (ILS, LGOT, RELATIVE)
MFC = "Возможность обращения через МФЦ зависит от региона и конкретной услуги"
FORBIDDEN = (
    "гарантируем",
    "увеличим пенсию",
    "добьёмся",
    "рассчитаем пенсию",
    "мфц.рф",
    "/blog/chto-delat-esli-period-raboty-ne-uchten/",
    "/blog/arhivnaya-spravka-dlya-sfr-zachem-i-kuda/",
    "/blog/kak-pomoch-rodstvenniku-proverit-stazh/",
)


def _entry(seed: Path, slug: str) -> dict[str, str]:
    text = seed.read_text(encoding="utf-8")
    m = re.search(rf"'slug' => '{slug}',(.*?)\n    \],", text, re.S)
    assert m, slug
    return dict(re.findall(r"'(title|seo_title|seo_description)' => '([^']*)'", m.group(1)))


def _html(page: dict) -> str:
    return page["file"].read_text(encoding="utf-8")


def test_seed_titles() -> None:
    for page, seed in ((ILS, BLOG_SEED), (LGOT, BLOG_SEED), (RELATIVE, TRUST_SEED)):
        entry = _entry(seed, page["slug"])
        assert entry["title"] == page["title"]
        assert entry["seo_title"] == page["seo_title"]
        assert len(entry["seo_title"]) <= 70
        assert 70 <= len(entry["seo_description"]) <= 160, page["slug"]


def test_blog_h1_equals_title_and_single() -> None:
    for page in (ILS, LGOT):
        assert re.findall(r"<h1[^>]*>(.*?)</h1>", _html(page), re.S) == [page["title"]]


def test_trust_page_has_no_h1_theme_renders_title() -> None:
    assert "<h1" not in _html(RELATIVE)


def test_blog_meta_description_in_sync() -> None:
    meta = SEO_META.read_text(encoding="utf-8")
    for page in (ILS, LGOT):
        m = re.search(rf"'{page['slug']}' => '([^']*)'", meta)
        assert m
        assert m.group(1) == _entry(BLOG_SEED, page["slug"])["seo_description"]


def test_key_sections_present() -> None:
    for page in PAGES:
        html = _html(page)
        for needle in page["must"]:
            assert needle in html, (page["slug"], needle)


def test_rules_submission_mfc_official_prices() -> None:
    for page in PAGES:
        html = _html(page)
        low = html.lower()
        assert "подаёте" in low and "сфр" in low, page["slug"]
        assert MFC in html, page["slug"]
        assert "https://www.gosuslugi.ru/" in html and "https://sfr.gov.ru/" in html
        for bad in FORBIDDEN:
            assert bad not in low, (page["slug"], bad)
        raw = re.findall(r"(\d[\d\s]*(?:&nbsp;\d+)?)\s*(?:&nbsp;)?₽", html)
        prices = {re.sub(r"\D", "", p) for p in raw}
        assert prices <= {"3000", "5000", "8000"}, (page["slug"], prices)
