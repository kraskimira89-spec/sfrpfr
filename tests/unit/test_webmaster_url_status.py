"""Статусы доработанных страниц в Вебмастере: разбор ответов API и сравнение со снимком."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
BASE = "https://proverkastaza.ru"


def _load() -> ModuleType:
    path = ROOT / "scripts/yandex_webmaster_url_status.py"
    spec = importlib.util.spec_from_file_location("yandex_webmaster_url_status", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


us = _load()

T = "T00:00:00.000+03:00"
IMPORTANT = {
    "urls": [
        {
            "url": f"{BASE}/otkaz-sfr/",
            "indexing_status": {"status": "HTTP_2XX", "access_date": f"2026-09-20{T}"},
            "search_status": {
                "searchable": False,
                "excluded_url_status": "LOW_QUALITY",
                "last_access": f"2026-09-19{T}",
            },
        },
        {
            "url": f"{BASE}/tarify/",
            "indexing_status": {"status": "HTTP_2XX", "access_date": f"2026-09-26{T}"},
            "search_status": {"searchable": True, "excluded_url_status": None},
        },
    ]
}
IN_SEARCH = {"count": 1, "samples": [{"url": f"{BASE}/blog/fio/", "last_access": f"2026-09-27{T}"}]}
INDEXING = {
    "count": 1,
    "samples": [{"url": f"{BASE}/blog/edv/", "access_date": f"2026-07-29{T}"}],
}
RECRAWL = {
    "count": 3,
    "tasks": [
        {"url": f"{BASE}/blog/fio/", "added_time": f"2026-09-27{T}", "state": "DONE"},
        {"url": f"{BASE}/blog/fio/", "added_time": f"2026-09-20{T}", "state": "FAILED"},
        {"url": f"{BASE}/blog/edv/", "added_time": f"2026-09-27{T}", "state": "IN_PROGRESS"},
    ],
}


def fake_api(method: str, path: str) -> tuple[int, dict]:
    assert method == "GET"
    if path.endswith("/important-urls"):
        return 200, IMPORTANT
    if "/search-urls/in-search/samples" in path:
        return 200, IN_SEARCH if "offset=0" in path else {"count": 1, "samples": []}
    if "/indexing/samples" in path:
        return 200, INDEXING if "offset=0" in path else {"count": 1, "samples": []}
    if "/recrawl/queue" in path:
        return 200, RECRAWL if "offset=0" in path else {"count": 3, "tasks": []}
    raise AssertionError(path)


TRACKED = [
    {"url": f"{BASE}/otkaz-sfr/", "group": "посадочная", "expected": "in_search"},
    {"url": f"{BASE}/blog/fio/", "group": "PR #102", "expected": "in_search"},
    {"url": f"{BASE}/blog/edv/", "group": "PR #102", "expected": "noindex"},
    {"url": f"{BASE}/blog/old/", "group": "PR #100", "expected": "redirect"},
]
LIVE = {
    f"{BASE}/otkaz-sfr/": {"code": 200, "location": None, "noindex": False},
    f"{BASE}/blog/fio/": {"code": 200, "location": None, "noindex": False},
    f"{BASE}/blog/edv/": {"code": 200, "location": None, "noindex": True},
    f"{BASE}/blog/old/": {"code": 301, "location": f"{BASE}/new/", "noindex": False},
}


def _snapshot() -> dict:
    return us.collect(fake_api, "https:proverkastaza.ru:443", "1", TRACKED, live=LIVE.get)


def test_collect_parses_all_sources() -> None:
    rows = {r["url"]: r for r in _snapshot()["urls"]}
    otkaz = rows[f"{BASE}/otkaz-sfr/"]
    assert otkaz["in_search"] is False and otkaz["excluded"] == "LOW_QUALITY"
    assert otkaz["last_crawl"] == "2026-09-20"
    fio = rows[f"{BASE}/blog/fio/"]
    assert fio["in_search"] is True and fio["recrawl"] == "DONE"
    edv = rows[f"{BASE}/blog/edv/"]
    assert edv["last_crawl"] == "2026-07-29" and edv["recrawl"] == "IN_PROGRESS"
    assert edv["live"]["noindex"] is True
    assert rows[f"{BASE}/blog/old/"]["live"]["code"] == 301
    assert f"{BASE}/tarify/" in rows, "мониторинг Вебмастера добавляется автоматически"


def test_expectation_check() -> None:
    rows = {r["url"]: r for r in _snapshot()["urls"]}
    assert rows[f"{BASE}/otkaz-sfr/"]["ok"] is False
    assert rows[f"{BASE}/blog/fio/"]["ok"] is True
    assert rows[f"{BASE}/blog/edv/"]["ok"] is True
    assert rows[f"{BASE}/blog/old/"]["ok"] is True


def test_diff_was_became() -> None:
    base = _snapshot()
    cur = json.loads(json.dumps(base))
    for row in cur["urls"]:
        if row["url"].endswith("/otkaz-sfr/"):
            row.update(in_search=True, excluded=None, last_crawl="2026-10-02", ok=True)
    changes = us.diff(base, cur)
    assert len(changes) == 1
    url, field_changes = changes[0]
    assert url.endswith("/otkaz-sfr/")
    assert ("статус", "исключена: LOW_QUALITY", "в поиске") in field_changes
    assert ("обход", "2026-09-20", "2026-10-02") in field_changes


def test_markdown_has_table_and_diff_without_queries() -> None:
    snap = _snapshot()
    md = us.render_markdown(snap, base=snap)
    assert "| URL |" in md and "было → стало" in md
    assert "исключена: LOW_QUALITY" in md
    assert "Изменений нет" in md


def test_tracked_config_is_valid() -> None:
    items = us.load_tracked(ROOT / "scripts/assets/seo/webmaster-tracked-urls.json")
    urls = [i["url"] for i in items]
    assert len(urls) == len(set(urls)) >= 15
    assert {i["expected"] for i in items} <= {"in_search", "noindex", "redirect"}
    assert all(u.startswith(BASE + "/") for u in urls)
    by_url = {i["url"]: i["expected"] for i in items}
    assert by_url[f"{BASE}/blog/edv-i-pensiya-chto-proveryat-otdelno/"] == "noindex"
    assert by_url[f"{BASE}/blog/arhivnaya-spravka-dlya-sfr-zachem-i-kuda/"] == "redirect"
