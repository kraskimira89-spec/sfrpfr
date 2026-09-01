#!/usr/bin/env python3
"""Проверка HTML-контента на запрещённые формулировки, обещания и каналы ПДн."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_FILE = ROOT / "docs" / "content" / "forbidden-claims.txt"
RESTRICTED_CHANNELS_FILE = ROOT / "docs" / "content" / "restricted-document-channel-phrases.txt"

# Исключения (с обоснованием):
# 1. Юридические документы (не изменяются автоматически без отдельной задачи владельца)
# 2. Прямые отрицания ("не гарантируем перерасчёт", "не обещаем", "не отправляйте в MAX")
ALLOWLIST_EXEMPT_FILES = {
    "sfrfr-oferta.html": "Оферта (раздел 7) — юридический документ, не меняется автоматически",
    "sfrfr-privacy.html": "Политика конфиденциальности — не меняется автоматически",
    "sfrfr-consent.html": "Согласие на обработку ПДн — не меняется автоматически",
}

NEGATION_PREFIXES = (
    "не ",
    "нет.",
    "без ",
    "отсутствие ",
    "исключ",
    "запрещ",
    "не являемся",
    "не передавайте",
    "не отправляйте",
    "не присылайте",
    "не пишите",
)


def load_phrases(file_path: Path, default_list: list[str]) -> list[str]:
    if not file_path.exists():
        return [p.lower().strip() for p in default_list]
    lines = file_path.read_text(encoding="utf-8").splitlines()
    return [line.strip().lower() for line in lines if line.strip() and not line.startswith("#")]


def check_file(path: Path, forbidden: list[str]) -> list[dict[str, str | int]]:
    filename = path.name
    if filename in ALLOWLIST_EXEMPT_FILES:
        return []

    content = path.read_text(encoding="utf-8")
    violations = []

    for line_no, line in enumerate(content.splitlines(), start=1):
        line_clean = " ".join(line.split()).lower()
        if not line_clean:
            continue

        for phrase in forbidden:
            if phrase in line_clean:
                # Проверяем, не является ли это фразой с отрицанием
                idx = line_clean.find(phrase)
                preceding = line_clean[max(0, idx - 40) : idx]
                if any(
                    preceding.endswith(neg) or neg in preceding[-25:]
                    for neg in NEGATION_PREFIXES
                ):
                    continue

                violations.append(
                    {
                        "file": str(path.relative_to(ROOT)),
                        "line": line_no,
                        "phrase": phrase,
                        "text": line.strip()[:120],
                    }
                )
    return violations


def main() -> int:
    default_claims = [
        "оплата за результат",
        "подтверждённом повышении",
        "подтвержденном повышении",
        "гарантируем перерасчёт",
        "гарантируем перерасчет",
        "гарантируем повышение",
        "вернём недоплату",
        "вернем недоплату",
        "пересчитаем пенсию",
        "перерассчитаем пенсию",
        "добьёмся повышения пенсии",
        "добьемся повышения пенсии",
        "гарантия результата",
    ]
    default_channels = [
        "документы в чат max",
        "документы — в чат max",
        "сканы в max",
        "отправьте документы в max",
        "отправить документы в max",
        "прикрепите документы в max",
        "трудовую в max",
        "выписку илс в max",
    ]

    forbidden_claims = load_phrases(FORBIDDEN_FILE, default_claims)
    restricted_channels = load_phrases(RESTRICTED_CHANNELS_FILE, default_channels)
    all_rules = sorted(set(forbidden_claims + restricted_channels))

    assets_dir = ROOT / "scripts" / "assets"
    html_files = sorted(assets_dir.rglob("*.html"))

    all_violations: list[dict[str, str | int]] = []
    for html_file in html_files:
        all_violations.extend(check_file(html_file, all_rules))

    if all_violations:
        print("[FAIL] Нарушения в публичном контенте (запрещённые фразы / каналы ПДн):")
        for v in all_violations:
            print(f"  - {v['file']}:{v['line']} -> [{v['phrase']}] {v['text']}")
        return 1

    total_f = len(html_files)
    total_p = len(all_rules)
    print(f"[OK] Проверка пройдена: {total_f} HTML-файлов проверено на {total_p} правил.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
