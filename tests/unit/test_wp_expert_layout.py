"""Вёрстка страниц экспертов: шапка-карточка, навигация по разделам, отдельный CSS."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRUST = ROOT / "scripts/assets/trust"
PAGES = (TRUST / "expert-lopakova.html", TRUST / "expert-bogdanovskiy.html")
EXPERT_CSS = ROOT / "scripts/assets/sfrfr-expert.css"
APPLY_CSS = ROOT / "scripts/wp_apply_landing_css.php"


def _html(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_page_scoped_by_expert_class() -> None:
    for page in PAGES:
        assert '<div class="sfrfr-landing sfrfr-expert-page">' in _html(page), page.name


def test_hero_has_facts_and_cta() -> None:
    for page in PAGES:
        html = _html(page)
        body = re.search(r'<div class="sfrfr-expert-hero__body">(.*?)<h2', html, re.S)
        assert body, page.name
        facts = re.findall(r'<li class="sfrfr-expert-fact">', body.group(1))
        assert 3 <= len(facts) <= 4, page.name
        assert 'class="sfrfr-cta-row sfrfr-expert-hero__cta"' in body.group(1)
        assert "{{MAX_BTN_URL}}" in body.group(1)


def test_section_nav_matches_headings() -> None:
    for page in PAGES:
        html = _html(page)
        nav = re.search(r'<nav class="sfrfr-expert-nav"[^>]*>(.*?)</nav>', html, re.S)
        assert nav, page.name
        anchors = re.findall(r'href="#([a-z-]+)"', nav.group(1))
        assert len(anchors) >= 4
        for anchor in anchors:
            assert f'<h2 id="{anchor}"' in html, anchor


def test_expert_css_is_separate_and_applied() -> None:
    css = EXPERT_CSS.read_text(encoding="utf-8")
    for cls in (
        ".sfrfr-expert-page",
        ".sfrfr-expert-fact",
        ".sfrfr-expert-nav",
        ".sfrfr-expert-materials",
        ".sfrfr-expert-info",
        ".sfrfr-expert-qualities-block",
        "scroll-margin-top",
        "@media (max-width: 767px)",
    ):
        assert cls in css, cls
    assert "sfrfr-expert.css" in APPLY_CSS.read_text(encoding="utf-8")


def test_qualities_grid_three_columns_on_desktop() -> None:
    css = EXPERT_CSS.read_text(encoding="utf-8")
    block = re.search(r"\.sfrfr-expert-qualities \{(.*?)\}", css, re.S)
    assert block
    # 5 пунктов: 3 + 2, без одинокой карточки в последнем ряду
    assert "minmax(300px, 1fr)" in block.group(1)
