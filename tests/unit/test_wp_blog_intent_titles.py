"""План каннибализации 2026-09-27, п. 2 и 5: title/H1 статей разведены с посадочными."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "scripts/wp_seed_blog_tz11.php"
SEO_META = ROOT / "scripts/wp-mu-plugins/sfrfr-seo-meta.php"
BLOG = ROOT / "scripts/assets/blog"

EXPECTED = {
    "otkaz-sfr-chto-proverit-v-dokumentah": {
        "file": "12-otkaz-sfr.html",
        "title": "Отказ СФР: как разобрать решение и подготовить повторное обращение",
        "seo_title": "Отказ СФР: что делать и как подготовить повторное обращение",
        "landing_prefixes": (
            "Не учли стаж",
            "Отказ в назначении пенсии",
            "Отказ СФР в назначении пенсии",
        ),
    },
    "severnyy-stazh-i-rayonnyy-koefficient": {
        "file": "17-severnyy-stazh.html",
        "title": "Северный стаж не учли в ИЛС: какие документы подтвердят период",
        "seo_title": "Северный стаж не учли: какие документы подтвердят период",
        "landing_prefixes": ("Северный стаж для пенсии",),
    },
}
FORBIDDEN = ("гарантир", "калькулятор", "сумм", "увеличим", "добьёмся")


def _seed_entry(slug: str) -> dict[str, str]:
    seed = SEED.read_text(encoding="utf-8")
    m = re.search(rf"'slug' => '{slug}',(.*?)'related'", seed, re.S)
    assert m, slug
    return dict(re.findall(r"'(title|seo_title|seo_description)' => '([^']*)'", m.group(1)))


def _meta_description(slug: str) -> str:
    m = re.search(rf"'{slug}' => '([^']*)'", SEO_META.read_text(encoding="utf-8"))
    assert m, slug
    return m.group(1)


def test_titles_split_from_landings() -> None:
    for slug, exp in EXPECTED.items():
        entry = _seed_entry(slug)
        assert entry["title"] == exp["title"]
        assert entry["seo_title"] == exp["seo_title"]
        for value in (entry["title"], entry["seo_title"]):
            assert not value.startswith(exp["landing_prefixes"]), value
            assert len(value) <= 70


def test_html_h1_matches_seed_title_and_single() -> None:
    for slug, exp in EXPECTED.items():
        html = (BLOG / exp["file"]).read_text(encoding="utf-8")
        h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        assert h1 == [exp["title"]], slug


def test_descriptions_in_sync_and_safe() -> None:
    for slug in EXPECTED:
        entry = _seed_entry(slug)
        meta = _meta_description(slug)
        assert entry["seo_description"] == meta
        assert 70 <= len(meta) <= 160, (slug, len(meta))
        low = meta.lower()
        assert not any(w in low for w in FORBIDDEN), meta


def test_seo_titles_unique_in_seed() -> None:
    seed = SEED.read_text(encoding="utf-8")
    titles = re.findall(r"'seo_title' => '([^']*)'", seed)
    assert len(titles) == len(set(titles))
