#!/usr/bin/env python3
"""Популярные запросы Яндекс Вебмастера + фильтр по ключам (H3/H5).

Env: secrets/yandex-webmaster.env
  YANDEX_WEBMASTER_OAUTH_ACCESS_TOKEN
  YANDEX_WEBMASTER_HOST_ID=https:proverkastaza.ru:443

Usage:
  python scripts/yandex_webmaster_search_queries.py
  python scripts/yandex_webmaster_search_queries.py --filter "калькулятор|расчет пенсии|расчёт пенсии"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API = "https://api.webmaster.yandex.net/v4"
ROOT = Path(__file__).resolve().parents[1]
NEEDLES_DEFAULT = (
    "калькулятор",
    "расчет пенсии",
    "расчёт пенсии",
    "калькулятор стажа",
    "пенсионный калькулятор",
)


def load_dotenv() -> None:
    for rel in ("secrets/yandex-webmaster.env", ".env"):
        path = ROOT / rel
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("\"'")
            if k and k not in os.environ:
                os.environ[k] = v


def api(method: str, path: str, query: dict[str, str | list[str]] | None = None) -> tuple[int, dict | list | None]:
    token = os.environ.get("YANDEX_WEBMASTER_OAUTH_ACCESS_TOKEN", "").strip()
    if not token or not token.startswith("y0"):
        raise SystemExit("Нужен YANDEX_WEBMASTER_OAUTH_ACCESS_TOKEN вида y0_…")
    qs_parts: list[str] = []
    if query:
        for key, val in query.items():
            if isinstance(val, list):
                for item in val:
                    qs_parts.append(f"{urllib.parse.quote(key)}={urllib.parse.quote(str(item))}")
            elif val is not None and str(val) != "":
                qs_parts.append(f"{urllib.parse.quote(key)}={urllib.parse.quote(str(val))}")
    url = f"{API}{path}"
    if qs_parts:
        url += "?" + "&".join(qs_parts)
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"OAuth {token}", "Accept": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(err)
        except json.JSONDecodeError:
            parsed = {"raw": err}
        return e.code, parsed


def indicator(row: dict, name: str) -> float | None:
    ind = row.get("indicators")
    if isinstance(ind, dict) and name in ind:
        try:
            return float(ind[name])
        except (TypeError, ValueError):
            return None
    if isinstance(ind, list):
        for item in ind:
            if not isinstance(item, dict):
                continue
            if str(item.get("name") or item.get("indicator") or "") == name:
                try:
                    return float(item.get("value"))
                except (TypeError, ValueError):
                    return None
    if name in row and isinstance(row[name], (int, float)):
        return float(row[name])
    return None


def query_text(row: dict) -> str:
    for key in ("query_text", "query", "text"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def main() -> int:
    load_dotenv()
    p = argparse.ArgumentParser(description="Яндекс Вебмастер: популярные запросы")
    p.add_argument("--filter", default="калькулятор|расчет пенсии|расчёт пенсии|стаж")
    p.add_argument("--limit", type=int, default=500)
    p.add_argument("--days", type=int, default=28)
    p.add_argument(
        "--out",
        type=Path,
        default=ROOT / "docs/marketing-sales/reports" / f"webmaster-queries-{date.today().isoformat()}.md",
    )
    args = p.parse_args()

    code, user = api("GET", "/user")
    if code != 200 or not isinstance(user, dict):
        raise SystemExit(f"GET /user failed: {code} {user}")
    uid = user.get("user_id")
    host_id = os.environ.get("YANDEX_WEBMASTER_HOST_ID", "https:proverkastaza.ru:443").strip()
    host_q = urllib.parse.quote(host_id, safe="")
    date_to = date.today()
    date_from = date_to - timedelta(days=max(1, args.days))
    path = f"/user/{uid}/hosts/{host_q}/search-queries/popular"
    query = {
        "order_by": "TOTAL_SHOWS",
        "query_indicator": ["TOTAL_SHOWS", "TOTAL_CLICKS", "AVG_SHOW_POSITION"],
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "limit": str(args.limit),
        "offset": "0",
    }
    code, data = api("GET", path, query)
    print(f"user_id={uid} host_id={host_id} popular={code}", flush=True)
    if code != 200:
        print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            f"# Запросы Вебмастера {date.today().isoformat()}\n\n"
            f"API `search-queries/popular` вернул **{code}**.\n\n"
            f"```json\n{json.dumps(data, ensure_ascii=False, indent=2)[:4000]}\n```\n\n"
            "Если 403 — у OAuth нет права на статистику запросов; выгрузить CSV из UI:\n"
            "https://webmaster.yandex.ru/site/https%3Aproverkastaza.ru%3A443/search/queries/\n",
            encoding="utf-8",
        )
        print(f"wrote {args.out}")
        return 0 if code in (403, 404) else 1

    rows = []
    if isinstance(data, dict):
        rows = data.get("queries") or data.get("popular_queries") or data.get("items") or []
    needle = re.compile(args.filter, re.IGNORECASE)
    parsed: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        text = query_text(row)
        shows = indicator(row, "TOTAL_SHOWS") or 0
        clicks = indicator(row, "TOTAL_CLICKS") or 0
        pos = indicator(row, "AVG_SHOW_POSITION")
        ctr = (clicks / shows * 100) if shows else 0.0
        rec = {
            "query": text,
            "shows": int(shows),
            "clicks": int(clicks),
            "ctr_pct": round(ctr, 2),
            "avg_pos": round(pos, 2) if pos is not None else None,
        }
        parsed.append(rec)
    parsed.sort(key=lambda r: r["shows"], reverse=True)
    matched = [r for r in parsed if r["query"] and needle.search(r["query"])]
    calcish = [
        r for r in matched
        if any(n in r["query"].casefold() for n in ("калькулятор", "расчет пенсии", "расчёт пенсии"))
    ]

    def table(recs: list[dict]) -> list[str]:
        out = [
            "| Запрос | Показы | Клики | CTR % | Ср. позиция |",
            "|---|---:|---:|---:|---:|",
        ]
        for rec in recs:
            pos = rec["avg_pos"] if rec["avg_pos"] is not None else "—"
            out.append(
                f"| {rec['query'] or '—'} | {rec['shows']} | {rec['clicks']} | {rec['ctr_pct']} | {pos} |"
            )
        return out

    lines = [
        f"# Запросы Вебмастера {date.today().isoformat()}",
        "",
        f"Хост: `{host_id}`. Период API: {date_from.isoformat()} — {date_to.isoformat()}.",
        f"Всего строк popular: **{len(parsed)}**. Фильтр `{args.filter}`: **{len(matched)}**.",
        "",
        "## Калькулятор / расчёт пенсии",
        "",
    ]
    if not calcish:
        lines.append(
            "Показов по «калькулятор*» / «расчёт пенсии» в выгрузке **нет** "
            "(сайт ещё не в выдаче по этим ключам или окно слишком короткое)."
        )
        lines.append("")
        lines.append("H3/H5: baseline = **0 показов**. Следующий съём — после переобхода ядра.")
        lines.append("")
    else:
        lines.extend(table(calcish))
        lines.append("")

    lines.extend(["## Совпадения фильтра", ""])
    if not matched:
        lines.append("_Пусто._")
        lines.append("")
    else:
        lines.extend(table(matched[:40]))
        lines.append("")

    lines.extend(["## Все popular-запросы (как есть)", ""])
    if not parsed:
        lines.append("_Пусто._")
        lines.append("")
    else:
        lines.extend(table(parsed[:50]))
        lines.append("")

    lines.extend(
        [
            "## Источник",
            "",
            f"`GET search-queries/popular` count={data.get('count') if isinstance(data, dict) else '?'}",
            "",
            "UI: https://webmaster.yandex.ru/site/https%3Aproverkastaza.ru%3A443/search/queries/",
            "",
        ]
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"matched={len(matched)} calcish={len(calcish)} wrote {args.out}")
    preview = calcish[:8] or matched[:8] or parsed[:8]
    print(json.dumps(preview, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
