"""Страницы P2 из seo-low-quality-recommendations-2026-09-27: ФИО — доработка, ЕДВ — noindex."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLOG_SEED = ROOT / "scripts/wp_seed_blog_tz11.php"
SEO_META = ROOT / "scripts/wp-mu-plugins/sfrfr-seo-meta.php"
REDIRECTS = ROOT / "scripts/wp-mu-plugins/sfrfr-seo-redirects.php"
REPAIR = ROOT / "scripts/wp_repair_seo_descriptions.php"

FIO_FILE = ROOT / "scripts/assets/blog/20-fio-trudovaya.html"
FIO_SLUG = "rashozhdeniya-fio-i-zapisi-trudovoy"
FIO_TITLE = "Ошибка в трудовой книжке в фамилии или дате: что делать для пенсии"
FIO_SEO_TITLE = "Ошибка в фамилии в трудовой книжке: как подтвердить стаж"
FIO_MUST = (
    "ошибка в фамилии",
    "свидетельство о заключении брака",
    "ликвидирован",
    "правопреемник",
    "<details",
    "/arhivnaya-spravka-stazh/",
    "/ne-uchli-stazh/",
    "/chek-list-dokumentov/",
    "/otkaz-sfr/",
)
EDV_SLUG = "edv-i-pensiya-chto-proveryat-otdelno"
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


def _entry(slug: str) -> dict[str, str]:
    text = BLOG_SEED.read_text(encoding="utf-8")
    m = re.search(rf"'slug' => '{slug}',(.*?)\n    \],", text, re.S)
    assert m, slug
    return dict(re.findall(r"'(title|seo_title|seo_description)' => '([^']*)'", m.group(1)))


def _noindex_slugs() -> list[str]:
    text = REDIRECTS.read_text(encoding="utf-8")
    m = re.search(r"function sfrfr_seo_noindex_post_slugs\(\): array\s*\{(.*?)\n\}", text, re.S)
    assert m, "нет списка noindex для постов"
    return re.findall(r"'([a-z0-9-]+)'", m.group(1))


def test_fio_seed_title() -> None:
    entry = _entry(FIO_SLUG)
    assert entry["title"] == FIO_TITLE
    assert entry["seo_title"] == FIO_SEO_TITLE
    assert len(entry["seo_title"]) <= 70
    assert 70 <= len(entry["seo_description"]) <= 160


def test_fio_single_h1_equals_title() -> None:
    html = FIO_FILE.read_text(encoding="utf-8")
    assert re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S) == [FIO_TITLE]


def test_fio_descriptions_in_sync() -> None:
    desc = _entry(FIO_SLUG)["seo_description"]
    for path in (SEO_META, REPAIR):
        m = re.search(rf"'{FIO_SLUG}' => '([^']*)'", path.read_text(encoding="utf-8"))
        assert m and m.group(1) == desc, path.name


def test_fio_content_rules() -> None:
    html = FIO_FILE.read_text(encoding="utf-8")
    low = html.lower()
    for needle in FIO_MUST:
        assert needle in low, needle
    assert "подаёте" in low and "решение принимает сфр" in low
    assert MFC in html
    assert "https://www.gosuslugi.ru/" in html and "https://sfr.gov.ru/" in html
    for bad in FORBIDDEN:
        assert bad not in low, bad
    raw = re.findall(r"(\d[\d\s]*(?:&nbsp;\d+)?)\s*(?:&nbsp;)?₽", html)
    assert {re.sub(r"\D", "", p) for p in raw} <= {"3000", "5000", "8000"}


def test_edv_noindex_follow_and_out_of_sitemap() -> None:
    assert _noindex_slugs() == [EDV_SLUG]
    redirects = REDIRECTS.read_text(encoding="utf-8")
    assert "sfrfr_seo_noindex_post_ids()" in redirects
    sitemap = r"wp_sitemaps_posts_query_args.*?sfrfr_seo_noindex_post_ids\(\)"
    assert re.search(sitemap, redirects, re.S)
    meta = SEO_META.read_text(encoding="utf-8")
    assert re.search(
        r"function sfrfr_seo_is_noindex\(\): bool.*?sfrfr_seo_is_noindex_post\(\)", meta, re.S
    )


def test_fio_is_indexable() -> None:
    assert FIO_SLUG not in _noindex_slugs()
    assert FIO_SLUG not in REDIRECTS.read_text(encoding="utf-8").split("function sfrfr_seo_thin")[0]
