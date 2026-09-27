"""План каннибализации 2026-09-27: 301 статей п. 1 и 4, noindex служебных страниц, часы работы."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MU = ROOT / "scripts/wp-mu-plugins"
REDIRECTS = MU / "sfrfr-seo-redirects.php"
ROBOTS = MU / "sfrfr-seo-robots.php"
SCHEMA = MU / "sfrfr-seo-schema.php"
SEO_META = MU / "sfrfr-seo-meta.php"
SEED = ROOT / "scripts/wp_seed_blog_tz11.php"

MERGED = {
    "/blog/chto-delat-esli-period-raboty-ne-uchten": "/ne-uchli-stazh/",
    "/blog/kak-pomoch-rodstvenniku-proverit-stazh": "/pomoch-rodstvenniku-proverit-stazh/",
}
NOINDEX_PAGES = ("anketa-otzyv", "chek-list-dokumentov/a4")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_body(php: str, name: str) -> str:
    m = re.search(rf"function {name}\([^)]*\)[^{{]*\{{(.*?)\n\}}", php, re.S)
    assert m, name
    return m.group(1)


def test_merged_redirect_map_points_to_landings() -> None:
    body = _function_body(_read(REDIRECTS), "sfrfr_seo_merged_redirect_map")
    pairs = dict(re.findall(r"'(/blog/[a-z0-9-]+)' => '(/[a-z0-9-]+/)'", body))
    assert pairs == MERGED


def test_merged_redirect_is_301_and_checked_in_template_redirect() -> None:
    php = _read(REDIRECTS)
    assert "sfrfr_seo_merged_redirect_map()" in php
    assert re.search(r"wp_safe_redirect\(home_url\(\$merged\[\$path\]\), 301\)", php)


def test_thin_redirects_have_no_chain_to_merged_articles() -> None:
    body = _function_body(_read(REDIRECTS), "sfrfr_seo_thin_redirect_map")
    for source in MERGED:
        assert source + "/" not in body, f"цепочка 301 через {source}"
    assert "'period' => '/ne-uchli-stazh/'" in body


def test_merged_articles_excluded_from_sitemap_and_blog_lists() -> None:
    php = _read(REDIRECTS)
    assert "add_filter('wp_sitemaps_posts_query_args'" in php
    assert "post__not_in" in php
    assert "add_action('pre_get_posts'" in php


def test_merged_article_links_rewritten_in_content() -> None:
    php = _read(REDIRECTS)
    assert "add_filter('the_content'" in php
    assert "function sfrfr_seo_merged_rewrite_links(" in php


def test_seed_skips_merged_articles() -> None:
    seed = _read(SEED)
    pattern = r"'slug' => '([a-z0-9-]+)',\s*'merged_into' => '(/[a-z0-9-]+/)'"
    merged = dict(re.findall(pattern, seed))
    assert merged == {k.removeprefix("/blog/"): v for k, v in MERGED.items()}
    assert "if (!empty($a['merged_into']))" in seed


def test_noindex_pages_list() -> None:
    body = _function_body(_read(ROBOTS), "sfrfr_seo_noindex_page_paths")
    assert tuple(re.findall(r"'([a-z0-9/-]+)'", body)) == NOINDEX_PAGES
    for kept in ("'chek-list-dokumentov'", "'chek-list-dokumentov/pechat'"):
        assert kept not in body


def test_noindex_pages_meta_header_and_sitemap() -> None:
    robots = _read(ROBOTS)
    assert "X-Robots-Tag: noindex, follow" in robots
    assert "add_filter('wp_sitemaps_posts_query_args'" in robots
    assert "post__not_in" in robots
    for path in NOINDEX_PAGES:
        assert f"Disallow: /{path}" not in robots, "noindex-страницы не закрывать в robots.txt"
    body = _function_body(_read(SEO_META), "sfrfr_seo_is_noindex")
    assert "sfrfr_seo_is_noindex_page()" in body


def test_local_business_opening_hours_mo_fr_9_18() -> None:
    php = _read(SCHEMA)
    assert "'openingHours'" in php
    assert "'Mo-Fr 09:00-18:00'" in php
