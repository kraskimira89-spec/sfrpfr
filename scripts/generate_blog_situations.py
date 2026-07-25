#!/usr/bin/env python3
"""Генерация HTML статей: 1 ситуация на клиента + аналитика каждые 5."""
from __future__ import annotations

import json
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


def main() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sit_by_id = {s["id"]: s for s in data["situations"]}
    index: list[dict] = []

    for s in data["situations"]:
        html = render_situation(s)
        name = f"{s['id'].lower()}-{s['slug']}.html"
        (OUT_DIR / name).write_text(html, encoding="utf-8")
        index.append(
            {
                "kind": "situation",
                "id": s["id"],
                "file": name,
                "slug": s["slug"],
                "title": s["title"],
                "category": s["category"],
                "excerpt": s["hook"][:180],
                "seo_title": s["title"][:60],
                "seo_description": s["hook"][:155],
            }
        )

    for a in data["analytics"]:
        html = render_analytics(a, sit_by_id)
        name = f"{a['id'].lower()}-{a['slug']}.html"
        (OUT_DIR / name).write_text(html, encoding="utf-8")
        index.append(
            {
                "kind": "analytics",
                "id": a["id"],
                "file": name,
                "slug": a["slug"],
                "title": a["title"],
                "category": a["category"],
                "excerpt": a["thesis"][:180],
                "seo_title": a["title"][:60],
                "seo_description": a["thesis"][:155],
            }
        )

    index_path = OUT_DIR / "index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK situations={len(data['situations'])} analytics={len(data['analytics'])} -> {OUT_DIR}")


if __name__ == "__main__":
    main()
