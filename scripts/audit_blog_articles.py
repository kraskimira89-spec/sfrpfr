#!/usr/bin/env python3
"""Статический редакционный аудит 16 основных HTML-статей."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BLOG = ROOT / "scripts" / "assets" / "blog"
CORE_FILES = tuple(BLOG / f"{number:02d}-{name}.html" for number, name in (
    (1, "ils-stazh"),
    (2, "trudovaya-ils"),
    (3, "period-ne-uchten"),
    (4, "arhivnaya-spravka"),
    (5, "tipichnye-situacii"),
    (6, "dlya-rodstvennikov"),
    (7, "chto-vy-poluchite"),
    (8, "max-i-kabinet"),
    (9, "faq-rasshirennyy"),
    (10, "dokumenty-do-sfr"),
    (11, "podacha-gosuslugi-mfc"),
    (12, "otkaz-sfr"),
    (13, "invalidnost-i-stazh"),
    (14, "diagnostika-vs-soprovozhdenie"),
    (15, "pochemu-reshenie-sfr"),
    (16, "chek-list-mfc"),
))

OFFICIAL_HOSTS = {"sfr.gov.ru", "www.gosuslugi.ru", "gosuslugi.ru"}
BANNED = (
    "через 2–3 месяца",
    "через 2-3 месяца",
    "срок годности",
    "удостоющий",
    "только в max",
    "гарантируем",
    "100%",
    "официально от сфр",
)


class AuditParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.h1 = 0
        self.h2 = 0
        self.links: list[str] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "h1":
            self.h1 += 1
        elif tag == "h2":
            self.h2 += 1
        elif tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def word_count(text: str) -> int:
    return len(re.findall(r"[А-Яа-яЁёA-Za-z0-9]+", text))


def main() -> int:
    failures: list[str] = []
    for path in CORE_FILES:
        if not path.is_file():
            failures.append(f"{path.name}: файл отсутствует")
            continue
        raw = path.read_text(encoding="utf-8")
        parser = AuditParser()
        parser.feed(raw)
        text = " ".join(parser.text)
        lower = text.lower()
        words = word_count(text)
        internal = [u for u in parser.links if u.startswith("/blog/")]
        official = [
            u for u in parser.links
            if urlparse(u).hostname in OFFICIAL_HOSTS
        ]
        errors: list[str] = []
        if parser.h1 != 1:
            errors.append(f"H1={parser.h1}")
        if parser.h2 < 4:
            errors.append(f"H2={parser.h2}<4")
        if not 700 <= words <= 1500:
            errors.append(f"слов={words}, нужно 700–1500")
        if len(internal) < 2:
            errors.append(f"внутренних ссылок={len(internal)}<2")
        if len(official) < 1:
            errors.append("нет официального источника")
        if "материал обновлён: 29 июля 2026 года" not in lower:
            errors.append("нет даты обновления")
        if "редакци" not in lower:
            errors.append("нет редакционной проверки")
        if "sfrfr-article-cta" in raw or "sfrfr-cta-row" in raw:
            errors.append("CTA внутри HTML (добавляет сидер)")
        for phrase in BANNED:
            if phrase in lower:
                errors.append(f"запрещённая фраза: {phrase}")
        if re.search(r"\b(?:\+7|8)\s*[\(\- ]?\d{3}", text):
            errors.append("похожий на телефон фрагмент")
        status = "OK" if not errors else "FAIL"
        print(
            f"{status} {path.name}: words={words} h1={parser.h1} "
            f"h2={parser.h2} internal={len(internal)} official={len(official)}"
        )
        failures.extend(f"{path.name}: {error}" for error in errors)

    if failures:
        print("\nОшибки:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"\nOK: audited {len(CORE_FILES)} core articles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
