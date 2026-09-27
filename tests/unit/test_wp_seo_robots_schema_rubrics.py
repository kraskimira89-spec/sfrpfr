"""Вебмастер, самопроверки: служебные URL (п. 12), микроразметка (п. 21), title рубрик блога."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MU = ROOT / "scripts/wp-mu-plugins"
ROBOTS = MU / "sfrfr-seo-robots.php"
SCHEMA = MU / "sfrfr-seo-schema.php"
ARCHIVES = MU / "sfrfr-seo-archives.php"
SEO_META = MU / "sfrfr-seo-meta.php"
FOOTER = MU / "sfrfr-site-footer.php"
DEPLOY_MU = ROOT / "scripts/wp_deploy_blog_ui.sh"
FAQ_ARTICLE = ROOT / "scripts/assets/blog/09-faq-rasshirennyy.html"
RUBRICS = ("ils", "stazh", "dokumenty", "podacha", "rodstvenniki", "usluga")
FORBIDDEN = ("гарант", "перерасчёт гарант", "увеличим", "подадим за вас", "подаём за вас")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_robots_closes_service_urls_inside_user_agent_group() -> None:
    php = _read(ROBOTS)
    for rule in (
        "Disallow: /?s=",
        "Disallow: /*?s=",
        "Disallow: /search/",
        "Disallow: /feed/",
        "Disallow: /*/feed/",
        "Disallow: /wp-json/",
    ):
        assert rule in php, rule
    assert "User-agent:" in php, "правила вставляются в группу User-agent: *"
    assert "Clean-param: utm_source" in php
    assert "Disallow: /blog/" not in php
    assert "Disallow: /wp-sitemap" not in php


def test_feeds_get_noindex_header() -> None:
    php = _read(ROBOTS)
    assert "is_feed()" in php
    assert "X-Robots-Tag: noindex" in php


def test_search_stays_noindex() -> None:
    meta = _read(SEO_META)
    assert re.search(r"function sfrfr_seo_is_noindex\(\): bool\s*\{.*?is_search\(\)", meta, re.S)


def test_astra_schema_disabled_and_footer_has_no_microdata() -> None:
    assert "add_filter('astra_schema_enabled', '__return_false')" in _read(SCHEMA)
    footer = _read(FOOTER)
    assert "itemscope" not in footer
    assert "itemprop=" not in footer


def test_local_business_same_as_real_profiles() -> None:
    php = _read(SCHEMA)
    assert "'sameAs'" in php
    for url in (
        "https://max.ru/channel_proverkastaza",
        "https://vk.com/proverkastaza",
        "https://yandex.ru/maps/org/proverka_stazha/82469923047/",
    ):
        assert url in php


def test_meta_exposes_graph_and_category_filters() -> None:
    meta = _read(SEO_META)
    assert "apply_filters('sfrfr_seo_schema_graph', $graph, $description, $canonical)" in meta
    assert "apply_filters('sfrfr_seo_category_description', ''" in meta


def _faq_pairs(html: str) -> list[tuple[str, str]]:
    """Та же логика, что в sfrfr_seo_schema_faq_from_content(): H2 с «?» + следующий <p>."""
    pairs = re.findall(r"<h2[^>]*>([^<]*\?)\s*</h2>\s*<p[^>]*>(.*?)</p>", html, re.S | re.I)
    return [(q.strip(), re.sub(r"<[^>]+>", "", a).strip()) for q, a in pairs]


def test_faq_article_has_visible_question_answer_pairs() -> None:
    php = _read(SCHEMA)
    assert "chastye-voprosy-o-proverke-stazha" in php
    assert "'FAQPage'" in php
    assert r"<h2[^>]*>([^<]*\?)\s*<\/h2>\s*(?:<!--.*?-->\s*)*<p[^>]*>(.*?)<\/p>" in php
    pairs = _faq_pairs(_read(FAQ_ARTICLE))
    assert len(pairs) >= 10
    assert any("Кто подаёт" in q for q, _ in pairs)


def test_article_image_prefers_post_thumbnail() -> None:
    php = _read(SCHEMA)
    assert "get_the_post_thumbnail_url" in php
    assert "'Article'" in php


def _rubric_meta() -> dict[str, tuple[str, str]]:
    php = _read(ARCHIVES)
    rows = re.findall(
        r"'([a-z]+)' => \[\s*'title' => '([^']+)',\s*'description' => '([^']+)',\s*\]",
        php,
    )
    return {slug: (title, desc) for slug, title, desc in rows}


def test_all_rubrics_have_meta() -> None:
    assert set(_rubric_meta()) == set(RUBRICS)


@pytest.mark.parametrize("slug", RUBRICS)
def test_rubric_title_and_description_length(slug: str) -> None:
    title, desc = _rubric_meta()[slug]
    assert 40 <= len(title) <= 70, (len(title), title)
    assert 100 <= len(desc) <= 160, (len(desc), desc)
    low = (title + " " + desc).lower()
    assert not any(word in low for word in FORBIDDEN)
    prices = {p.replace(" ", "") for p in re.findall(r"\d[\d ]*\d{3}", desc)}
    assert prices <= {"3000", "5000", "8000"}


def test_rubric_titles_unique_and_people_lexicon() -> None:
    meta = _rubric_meta()
    titles = [t for t, _ in meta.values()]
    assert len(set(titles)) == len(titles)
    assert "выписка илс" in meta["ils"][0].lower()
    assert "стаж" in meta["stazh"][0].lower()
    assert "архивн" in meta["dokumenty"][0].lower()
    assert "отказ сфр" in meta["podacha"][0].lower()
    assert "родственник" in meta["rodstvenniki"][0].lower()


def test_new_mu_plugins_are_deployed() -> None:
    sh = _read(DEPLOY_MU)
    for name in ("sfrfr-seo-schema.php", "sfrfr-seo-archives.php"):
        assert f'cp -f "${{ROOT}}/scripts/wp-mu-plugins/{name}"' in sh
