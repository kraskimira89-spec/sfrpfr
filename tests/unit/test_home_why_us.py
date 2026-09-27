"""Главная: блок «Почему мы» (Вебмастер, самопроверка п. 15 — УТП и отличия)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOME = ROOT / "scripts/assets/sfrfr-home.html"
CANON = (
    "Мы готовим документы, проект обращения и понятный план. Мы расскажем по шагам, "
    "но обращение через СФР, МФЦ или Госуслуги подаёте вы сами. "
    "Решение о пенсии и перерасчёте принимает только СФР."
)


def _block() -> str:
    html = HOME.read_text(encoding="utf-8")
    m = re.search(r'<section class="[^"]*" id="pochemu-my">(.*?)</section>', html, re.S)
    assert m, "секция #pochemu-my не найдена"
    return m.group(1)


def test_why_us_block_placed_before_tariffs() -> None:
    html = HOME.read_text(encoding="utf-8")
    assert html.index('id="otzyvy"') < html.index('id="pochemu-my"') < html.index('id="tarify"')
    assert '<section class="sfrfr-section sfrfr-section--alt" id="pochemu-my">' in html


def test_why_us_has_3_to_5_points() -> None:
    cards = re.findall(r'<article class="sfrfr-card">', _block())
    assert 3 <= len(cards) <= 5


def test_why_us_keeps_submission_position() -> None:
    assert CANON in _block()


def test_why_us_only_public_prices_and_no_promises() -> None:
    block = _block().replace("&nbsp;", " ")
    prices = {p.replace(" ", "") for p in re.findall(r"\d[\d ]*\d{3}(?=\s*₽)", block)}
    assert prices == {"3000", "5000", "8000"}
    text = re.sub(r"<[^>]+>", " ", block).lower()
    forbidden = (
        "гарантируем",
        "увеличим",
        "подадим за вас",
        "подаём за вас",
        "клиентов",
        "лет опыта",
    )
    for bad in forbidden:
        assert bad not in text, bad
