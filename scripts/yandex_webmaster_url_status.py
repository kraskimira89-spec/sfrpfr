#!/usr/bin/env python3
"""Статусы отслеживаемых страниц в Вебмастере и сравнение с базовым снимком (было → стало).

Источники API v4: important-urls, search-urls/in-search/samples, indexing/samples, recrawl/queue;
плюс живой ответ сайта (код, Location, noindex). Поисковые запросы посетителей не читаются.

Env: secrets/yandex-webmaster.env → YANDEX_WEBMASTER_OAUTH_ACCESS_TOKEN

Usage:
  python scripts/yandex_webmaster_url_status.py                  # таблица + сравнение с базой
  python scripts/yandex_webmaster_url_status.py --summary        # + в $GITHUB_STEP_SUMMARY
  python scripts/yandex_webmaster_url_status.py --save-baseline base.json --out report.md
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
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "scripts/assets/seo/webmaster-tracked-urls.json"
BASELINE = ROOT / "docs/marketing-sales/reports/seo-page-status-baseline-2026-09-27.json"
HOST_ID = "https:proverkastaza.ru:443"
EXPECTED_LABEL = {"in_search": "в поиске", "noindex": "noindex, выпасть", "redirect": "301 → цель"}

ApiFn = Callable[[str, str], tuple[int, Any]]
LiveFn = Callable[[str], "dict[str, Any] | None"]


def load_tracked(path: Path) -> list[dict[str, str]]:
    items = json.loads(path.read_text(encoding="utf-8"))["urls"]
    return [
        {"url": i["url"], "group": i.get("group", ""), "expected": i["expected"]} for i in items
    ]


def _day(value: object) -> str | None:
    return str(value)[:10] if value else None


def _pages(api: ApiFn, path: str, key: str, max_pages: int = 10) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    limit = 100
    for page in range(max_pages):
        code, data = api("GET", f"{path}?limit={limit}&offset={page * limit}")
        if code != 200 or not isinstance(data, dict):
            break
        chunk = data.get(key) or []
        out += chunk
        if len(chunk) < limit or len(out) >= int(data.get("count") or 0):
            break
    return out


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def live_check(url: str) -> dict[str, Any] | None:
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 sfrfr-status"})
    try:
        with opener.open(req, timeout=30) as resp:
            code, headers = resp.status, resp.headers
            body = resp.read(300_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return {"code": e.code, "location": e.headers.get("Location"), "noindex": False}
    except (urllib.error.URLError, TimeoutError):
        return None
    meta = re.search(r'<meta[^>]+name=["\']robots["\'][^>]*content=["\']([^"\']*)', body, re.I)
    robots = f"{headers.get('X-Robots-Tag', '')} {meta.group(1) if meta else ''}".lower()
    return {"code": code, "location": None, "noindex": "noindex" in robots}


def _status_label(row: dict[str, Any]) -> str:
    if row.get("in_search"):
        return "в поиске"
    if row.get("excluded"):
        return f"исключена: {row['excluded']}"
    return "нет в поиске"


def _live_label(live: dict[str, Any] | None) -> str:
    if not live:
        return "—"
    if live.get("location"):
        target = urllib.parse.urlsplit(str(live["location"])).path
        return f"{live['code']} → {target}"
    return f"{live['code']}{', noindex' if live.get('noindex') else ''}"


def _is_ok(row: dict[str, Any]) -> bool:
    live = row.get("live") or {}
    expected = row["expected"]
    if expected == "in_search":
        return bool(row["in_search"]) and not row["excluded"] and live.get("code", 200) == 200
    if expected == "noindex":
        return not row["in_search"] and live.get("noindex", True) is True
    return not row["in_search"] and live.get("code") in (301, 308)


def collect(
    api: ApiFn,
    host_id: str,
    uid: str,
    tracked: list[dict[str, str]],
    live: LiveFn | None = live_check,
) -> dict[str, Any]:
    base = f"/user/{uid}/hosts/{urllib.parse.quote(host_id, safe='')}"
    code, data = api("GET", f"{base}/important-urls")
    important = {u["url"]: u for u in (data or {}).get("urls", [])} if code == 200 else {}
    in_search = {s["url"] for s in _pages(api, f"{base}/search-urls/in-search/samples", "samples")}
    indexing = {s["url"]: s for s in _pages(api, f"{base}/indexing/samples", "samples")}
    recrawl: dict[str, dict[str, Any]] = {}
    for task in _pages(api, f"{base}/recrawl/queue", "tasks", max_pages=3):
        prev = recrawl.get(task["url"])
        if prev is None or str(task.get("added_time")) > str(prev.get("added_time")):
            recrawl[task["url"]] = task

    items = list(tracked)
    known = {i["url"] for i in items}
    items += [
        {"url": u, "group": "мониторинг Вебмастера", "expected": "in_search"}
        for u in important
        if u not in known
    ]
    rows = []
    for item in items:
        url = item["url"]
        imp = important.get(url)
        if imp:
            search = imp.get("search_status") or {}
            indexed = imp.get("indexing_status") or {}
            found = bool(search.get("searchable")) or url in in_search
            excluded = None if found else search.get("excluded_url_status")
            crawl = _day(indexed.get("access_date"))
        else:
            found, excluded = url in in_search, None
            crawl = _day((indexing.get(url) or {}).get("access_date"))
        row: dict[str, Any] = {
            **item,
            "in_search": found,
            "excluded": excluded,
            "last_crawl": crawl,
            "recrawl": (recrawl.get(url) or {}).get("state"),
            "monitored": imp is not None,
            "live": live(url) if live else None,
        }
        row["status"] = _status_label(row)
        row["ok"] = _is_ok(row)
        rows.append(row)
    return {"generated": datetime.now().astimezone().isoformat(timespec="minutes"), "urls": rows}


def _fields(row: dict[str, Any]) -> dict[str, str]:
    return {
        "статус": _status_label(row),
        "обход": row.get("last_crawl") or "—",
        "переобход": row.get("recrawl") or "—",
        "ответ": _live_label(row.get("live")),
        "цель": "✅" if row.get("ok") else "⏳",
    }


def diff(base: dict[str, Any], cur: dict[str, Any]) -> list[tuple[str, list[tuple[str, str, str]]]]:
    old = {r["url"]: _fields(r) for r in base["urls"]}
    out = []
    for row in cur["urls"]:
        was = old.get(row["url"])
        now = _fields(row)
        if was is None:
            out.append((row["url"], [("добавлен", "—", now["статус"])]))
            continue
        changed = [(k, was[k], now[k]) for k in now if was[k] != now[k]]
        if changed:
            out.append((row["url"], changed))
    return out


def _path(url: str) -> str:
    return urllib.parse.urlsplit(url).path or "/"


def render_markdown(snap: dict[str, Any], base: dict[str, Any] | None = None) -> str:
    rows = snap["urls"]
    ok = sum(1 for r in rows if r["ok"])
    lines = [
        f"## Статусы страниц в Вебмастере — {snap['generated']}",
        "",
        f"Цель достигнута: **{ok} из {len(rows)}**. "
        "✅ — статус совпал с ожидаемым, ⏳ — ещё нет. "
        "Поисковые запросы посетителей не выгружаются.",
        "",
        "| URL | Группа | Ожидаем | Статус в поиске | Обход | Переобход | Ответ сайта | Цель |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        f = _fields(r)
        lines.append(
            f"| `{_path(r['url'])}` | {r['group']} | {EXPECTED_LABEL[r['expected']]} "
            f"| {f['статус']} | {f['обход']} | {f['переобход']} | {f['ответ']} | {f['цель']} |"
        )
    if base is not None:
        lines += ["", f"### Сравнение с базовым снимком {base['generated']} (было → стало)", ""]
        changes = diff(base, snap)
        if not changes:
            lines.append("Изменений нет.")
        for url, items in changes:
            parts = "; ".join(f"{k}: {a} → {b}" for k, a, b in items)
            lines.append(f"- `{_path(url)}` — {parts}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Статусы отслеживаемых URL в Вебмастере")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--baseline", type=Path, default=BASELINE, help="снимок для сравнения")
    parser.add_argument("--save-baseline", type=Path, help="сохранить текущий снимок как JSON")
    parser.add_argument("--out", type=Path, help="записать markdown в файл")
    parser.add_argument("--no-live", action="store_true", help="без запроса к сайту")
    parser.add_argument("--summary", action="store_true", help="дописать в $GITHUB_STEP_SUMMARY")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import yandex_webmaster_diagnostics as wm

    wm.load_dotenv()
    code, user = wm.api("GET", "/user")
    if code != 200 or not isinstance(user, dict):
        raise SystemExit(f"/user {code}")
    host = os.environ.get("YANDEX_WEBMASTER_HOST_ID", HOST_ID)
    snap = collect(wm.api, host, str(user["user_id"]), load_tracked(args.config),
                   live=None if args.no_live else live_check)
    base = None
    if args.baseline.is_file() and args.baseline != args.save_baseline:
        base = json.loads(args.baseline.read_text(encoding="utf-8"))
    md = render_markdown(snap, base)
    if args.save_baseline:
        text = json.dumps(snap, ensure_ascii=False, indent=1) + "\n"
        args.save_baseline.write_text(text, encoding="utf-8")
    if args.out:
        args.out.write_text(md, encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if args.summary and summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(md)
    sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
