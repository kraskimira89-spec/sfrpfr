"""Title главной и коротких страниц + один H1 на странице WordPress (Вебмастер, п. 20)."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SEO_META = ROOT / "scripts/wp-mu-plugins/sfrfr-seo-meta.php"
SEO_H1 = ROOT / "scripts/wp-mu-plugins/sfrfr-seo-h1.php"
TRUST_SEED = ROOT / "scripts/wp_seed_trust_pages_tz18.php"
DEPLOY_MU = ROOT / "scripts/wp_deploy_blog_ui.sh"
TRUST_ASSETS = ROOT / "scripts/assets/trust"
SITE_SUFFIX = " — Проверка стажа"
LEADING_H1 = r"/^\s*(?:<!--.*?-->\s*)*<h1\b[^>]*>.*?<\/h1>\s*/isu"
FORBIDDEN = ("перерасч", "сумм", "гарант")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _front_title() -> str:
    m = re.search(r"if \(is_front_page\(\)\) \{\s*\$parts\['title'\] = '([^']+)';", _read(SEO_META))
    assert m, "title главной не найден в document_title_parts"
    return m.group(1)


def _blog_title() -> str:
    m = re.search(
        r"if \(is_home\(\) && !is_front_page\(\)\) \{\s*\$parts\['title'\] = '([^']+)';",
        _read(SEO_META),
    )
    assert m, "title /blog/ не найден"
    return m.group(1)


def _seed_seo_title(slug: str) -> str:
    m = re.search(
        rf"'slug' => '{re.escape(slug)}',\s*'title' => '[^']*',\s*'file' => '[^']*',"
        r"\s*'seo_title' => '([^']+)'",
        _read(TRUST_SEED),
    )
    assert m, f"seo_title для {slug} не найден"
    return m.group(1)


def _with_suffix(title: str) -> str:
    return title if title.endswith(SITE_SUFFIX) else title + SITE_SUFFIX


def test_front_title_has_people_lexicon_and_length() -> None:
    title = _front_title()
    assert 50 <= len(title) <= 70, (len(title), title)
    low = title.lower()
    assert "проверка стажа" in low
    assert "не учли стаж" in low
    assert "архивн" in low
    assert not any(word in low for word in FORBIDDEN)


def test_front_description_matches_title() -> None:
    m = re.search(r"if \(is_front_page\(\)\) \{\s*return '([^']+)';", _read(SEO_META))
    assert m
    desc = m.group(1)
    assert 71 <= len(desc) <= 160, (len(desc), desc)
    low = desc.lower()
    assert "не учли стаж" in low
    assert "архивн" in low
    assert "ИЛС" in desc
    assert "решение принимает СФР" in desc
    assert "перерасч" not in low


@pytest.mark.parametrize("slug", ["tarify", "kontakty", "otzyvy"])
def test_short_trust_titles_extended(slug: str) -> None:
    full = _with_suffix(_seed_seo_title(slug))
    assert 40 <= len(full) <= 70, (len(full), full)
    assert not any(word in full.lower() for word in FORBIDDEN)


def test_tariff_title_has_only_public_prices() -> None:
    title = _seed_seo_title("tarify")
    assert "3 000" in title and "5 000" in title and "8 000 ₽" in title
    prices = re.findall(r"\d[\d\s]*\d{3}", title)
    assert {p.replace(" ", "") for p in prices} == {"3000", "5000", "8000"}


def test_expert_hub_title_extended() -> None:
    m = re.search(
        r"update_post_meta\(\(int\) \$expertParent->ID, '_rank_math_title', '([^']+)'\)",
        _read(TRUST_SEED),
    )
    assert m
    full = _with_suffix(m.group(1))
    assert 40 <= len(full) <= 70, (len(full), full)
    assert "стаж" in full


def test_blog_title_extended() -> None:
    full = _with_suffix(_blog_title())
    assert 40 <= len(full) <= 70, (len(full), full)
    assert "ИЛС" in full


def test_mu_title_map_matches_seed() -> None:
    meta = _read(SEO_META)
    for slug in ("tarify", "kontakty", "otzyvy"):
        assert f"'{slug}' => '{_seed_seo_title(slug)}'" in meta


def test_seo_h1_plugin_disables_astra_title_only_on_pages() -> None:
    php = _read(SEO_H1)
    assert "add_filter('astra_the_title_enabled'" in php
    assert "is_page()" in php
    assert LEADING_H1 in php
    assert LEADING_H1 in _read(SEO_META), "регэксп снятия ведущего H1 должен совпадать"
    assert 'cp -f "${ROOT}/scripts/wp-mu-plugins/sfrfr-seo-h1.php"' in _read(DEPLOY_MU)


def _rendered_h1_count(content: str) -> int:
    """Логика MU: ведущий H1 снимается; тема выводит свой H1, только если в контенте H1 нет."""
    leading = r"^\s*(?:<!--.*?-->\s*)*<h1\b[^>]*>.*?</h1>\s*"
    rest = re.sub(leading, "", content, count=1, flags=re.S | re.I)
    own = len(re.findall(r"<h1\b", rest, flags=re.I))
    theme = 0 if own else 1
    return own + theme


@pytest.mark.parametrize("asset", sorted(p.name for p in TRUST_ASSETS.glob("*.html")))
def test_trust_page_renders_single_h1(asset: str) -> None:
    assert _rendered_h1_count(_read(TRUST_ASSETS / asset)) == 1
