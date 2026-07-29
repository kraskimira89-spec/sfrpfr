#!/usr/bin/env python3
"""Генерация HTML из manifest.json (АВАРИЙНЫЙ / LEGACY).

Политика SFRFR (с 2026-07-29):
- серии situacii/analitika и статьи блога дальше правятся ТОЛЬКО вручную;
- ИИ может давать рекомендации, но не перегенерирует и не пересиживает контент;
- массовый generate/seed запрещён без явного флага.

Запуск (только осознанно):
  SFRFR_ALLOW_SITUATIONS_GENERATE=1 python scripts/generate_blog_situations.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts" / "assets" / "blog" / "situations" / "manifest.json"
OUT_DIR = ROOT / "scripts" / "assets" / "blog" / "situations" / "html"


def _ul(items: list[str]) -> str:
    lis = "\n".join(f"  <li>{x}</li>" for x in items)
    return f"<ul>\n{lis}\n</ul>"


def _ol(items: list[str]) -> str:
    lis = "\n".join(f"  <li>{x}</li>" for x in items)
    return f"<ol>\n{lis}\n</ol>"


def _clip(text: str, limit: int) -> str:
    """Обрезка по символам без разрыва слова; без усечения коротких строк."""
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    cut = value[: max(1, limit - 1)].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0].rstrip(" ,.;:—-")
    return cut + "…"


def render_situation(s: dict) -> str:
    return f"""<h1>{s['title']}</h1>

<p class="sfrfr-example-badge"><em>Пример ситуации.</em> Обезличенное описание по типовым делам. Без ФИО, адресов и номеров документов.</p>

<p><strong>Короткий ответ.</strong> {s['hook']}</p>

<h2>Что за ситуация</h2>
<p>{s['situation']}</p>

<h2>Что обычно проверяют</h2>
{_ul(s['checked'])}

<h2>Что часто находят</h2>
{_ul(s['findings'])}

<h2>Какие документы понадобятся</h2>
{_ul(s['documents'])}

<h2>Что делать дальше</h2>
{_ol(s['next_steps'])}

<h2>Когда имеет смысл обратиться за разбором</h2>
<p>Если таблица периодов не сходится или непонятно, какой документ закрывает пробел, можно пройти диагностику. Мы не обещаем исход дела и не являемся СФР — помогаем собрать понятный план.</p>
"""


def render_analytics(a: dict, sit_by_id: dict[str, dict]) -> str:
    related_items = [f"«{sit_by_id[sid]['title']}»" for sid in a["after_situations"]]
    return f"""<h1>{a['title']}</h1>

<p class="sfrfr-example-badge"><em>Аналитическая статья.</em> Обобщение по пяти обезличенным примерам ситуаций. Без персональных данных.</p>

<p><strong>Тезис.</strong> {a['thesis']}</p>

<h2>Повторяющиеся закономерности</h2>
{_ul(a['patterns'])}

<h2>На каких примерах опираемся</h2>
{_ul(related_items)}

<h2>Практический чек-лист</h2>
{_ol(a['checklist'])}

<h2>Важно</h2>
<p>Это обобщение опыта разбора документов, а не статистика обещаний. Решение о перерасчёте и выплатах принимает только СФР.</p>
"""


def main() -> int:
    if os.environ.get("SFRFR_ALLOW_SITUATIONS_GENERATE", "").strip() != "1":
        print(
            "REFUSED: массовая генерация situations/analitika запрещена.\n"
            "Политика: только ручное редактирование HTML/index.json;\n"
            "ИИ — рекомендации, без перезаписи файлов.\n"
            "Аварийный обход: SFRFR_ALLOW_SITUATIONS_GENERATE=1",
            file=sys.stderr,
        )
        return 2

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sit_by_id = {s["id"]: s for s in data["situations"]}
    index: list[dict] = []

    for s in data["situations"]:
        html = render_situation(s)
        name = f"{s['id'].lower()}-{s['slug']}.html"
        (OUT_DIR / name).write_text(html, encoding="utf-8", newline="\n")
        title = str(s["title"]).strip()
        hook = str(s["hook"]).strip()
        index.append(
            {
                "kind": "situation",
                "id": s["id"],
                "file": name,
                "slug": s["slug"],
                "title": title,
                "category": s["category"],
                "excerpt": _clip(hook, 180),
                "seo_title": title,  # не резать посередине слова
                "seo_description": _clip(hook, 155),
            }
        )

    for a in data["analytics"]:
        html = render_analytics(a, sit_by_id)
        name = f"{a['id'].lower()}-{a['slug']}.html"
        (OUT_DIR / name).write_text(html, encoding="utf-8", newline="\n")
        title = str(a["title"]).strip()
        thesis = str(a["thesis"]).strip()
        index.append(
            {
                "kind": "analytics",
                "id": a["id"],
                "file": name,
                "slug": a["slug"],
                "title": title,
                "category": a["category"],
                "excerpt": _clip(thesis, 180),
                "seo_title": title,
                "seo_description": _clip(thesis, 155),
            }
        )

    index_path = OUT_DIR / "index.json"
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"OK situations={len(data['situations'])} analytics={len(data['analytics'])} -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
