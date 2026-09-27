"""Страницы экспертов (LOW_QUALITY P3): резюме под фото, материалы, публикации, Person."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRUST = ROOT / "scripts/assets/trust"
LOPAKOVA = TRUST / "expert-lopakova.html"
BOGDAN = TRUST / "expert-bogdanovskiy.html"
BLOG_SEED = ROOT / "scripts/wp_seed_blog_tz11.php"
REDIRECTS = ROOT / "scripts/wp-mu-plugins/sfrfr-seo-redirects.php"
SEO_META = ROOT / "scripts/wp-mu-plugins/sfrfr-seo-meta.php"
CSS = ROOT / "scripts/assets/sfrfr-landing.css"

VERIFIED = {
    LOPAKOVA: {
        "https://sever-press.ru/news/sever-press/predprinimateli-iz-nojabrska-pobedili-vo-vserossijskom-konkurse-socialnyh-proektov/",
        "https://ks-yanao.ru/news/obschestvo/kozhevennaya-masterskaya-ozdorovitelnye-zanyatiya-i-detskaya-ploshchadka-novye-sotsproekty-na-yamale",
        "https://podprismotrom89.ru/about",
        "https://entuziastov75.ru/rekvizity/",
    },
    BOGDAN: {
        "https://smotrim.ru/video/2903052",
        "https://yamal.aif.ru/society/dorogami-dobra",
        "https://yamal.aif.ru/society/details/v_noyabrske_pochti_v_tri_raza_vyrosla_potrebnost_v_socialnom_taksi",
        "https://taganai89.ru/profile/predsedatel/",
        "https://taganai89.ru/project/proekt-doroga-dobra/",
        "https://ekspertiyamala.ru/bogdanovskysergei",
        "https://dobro.ru/volunteers/870030",
    },
}
BANNED_HOSTS = (
    "checko",
    "rusprofile",
    "companium",
    "reputation.ru",
    "firmalyze",
    "zoon",
    "vk.com",
    "list-org",
)


def _html(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(html: str, title: str) -> str:
    pattern = rf"<h2[^>]*>{re.escape(title)}</h2>(.*?)(?=<h2|<!-- SFRFR_FEEDBACK_FORM)"
    m = re.search(pattern, html, re.S)
    assert m, title
    return m.group(1)


def test_no_h1_in_content_theme_renders_title() -> None:
    for page in (LOPAKOVA, BOGDAN):
        assert "<h1" not in _html(page)


def test_summary_and_qualities_under_photo() -> None:
    for page in (LOPAKOVA, BOGDAN):
        html = _html(page)
        side = re.search(r'<div class="sfrfr-expert-side">(.*?)</aside>\s*</div>', html, re.S)
        assert side, page.name
        block = side.group(1)
        assert block.index("sfrfr-expert-photo") < block.index("sfrfr-expert-summary")
        summary = re.search(r'<p class="sfrfr-expert-summary__text">(.*?)</p>', block, re.S)
        assert summary and 120 <= len(summary.group(1)) <= 420
        qualities = re.search(r'<ul class="sfrfr-expert-qualities">(.*?)</ul>', block, re.S)
        assert qualities
        assert 4 <= len(re.findall(r"<li>", qualities.group(1))) <= 6
    css = CSS.read_text(encoding="utf-8")
    for cls in (".sfrfr-expert-side", ".sfrfr-expert-summary", ".sfrfr-expert-qualities"):
        assert cls in css


def _live_blog_slugs() -> set[str]:
    seed = BLOG_SEED.read_text(encoding="utf-8")
    slugs = set()
    for block in re.findall(r"\[\s*'file' => .*?\n    \],", seed, re.S):
        slug = re.search(r"'slug' => '([^']+)'", block)
        if slug and "merged_into" not in block:
            slugs.add(slug.group(1))
    redirects = REDIRECTS.read_text(encoding="utf-8")
    pattern = r"function sfrfr_seo_noindex_post_slugs\(\): array\s*\{(.*?)\n\}"
    noindex = re.search(pattern, redirects, re.S)
    assert noindex
    return slugs - set(re.findall(r"'([a-z0-9-]+)'", noindex.group(1)))


def test_reviewed_materials_only_live_posts() -> None:
    block = _section(_html(LOPAKOVA), "Материалы, проверенные экспертом")
    slugs = re.findall(r'href="/blog/([a-z0-9-]+)/"', block)
    assert len(slugs) >= 10
    assert set(slugs) <= _live_blog_slugs()
    assert "Материалы, проверенные экспертом" not in _html(BOGDAN)


def test_publications_verified_and_safe() -> None:
    for page, allowed in VERIFIED.items():
        block = _section(_html(page), "Публикации и проекты")
        links = re.findall(r'<a href="(https?://[^"]+)"([^>]*)>', block)
        external = {href for href, _ in links if "proverkastaza.ru" not in href}
        assert external == allowed, page.name
        for href, attrs in links:
            if "proverkastaza.ru" in href:
                continue
            assert 'target="_blank"' in attrs and "nofollow" in attrs and "noopener" in attrs, href
        for item in re.findall(r"<li>(.*?)</li>", block, re.S):
            assert re.search(r"20\d\d", item), item
        low = block.lower()
        assert "инн" not in low and "tel:" not in low
        for host in BANNED_HOSTS:
            assert host not in low


def test_person_schema_same_as_and_knows_about() -> None:
    meta = SEO_META.read_text(encoding="utf-8")
    for name, same_as in (
        ("Лопакова Наталия Федоровна", ("https://podprismotrom89.ru/about",)),
        (
            "Богдановский Сергей Викторович",
            (
                "https://taganai89.ru/profile/predsedatel/",
                "https://ekspertiyamala.ru/bogdanovskysergei",
                "https://dobro.ru/volunteers/870030",
            ),
        ),
    ):
        m = re.search(rf"'name' => '{name}',(.*?)\n {{4,8}}\];", meta, re.S)
        assert m, name
        person = m.group(1)
        assert "'knowsAbout' =>" in person
        for url in same_as:
            assert url in person, url
