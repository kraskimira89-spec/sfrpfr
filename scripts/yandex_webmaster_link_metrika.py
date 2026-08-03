#!/usr/bin/env python3
"""Проверка связки Вебмастер ↔ Метрика и всё, что можно сделать по API.

Привязка счётчика и «Обход по счётчикам» в публичном API Яндекса отсутствуют
(все POST/PUT к /metrika/* → 404). Эти два шага — только UI.

Env:
  secrets/yandex-webmaster.env
  secrets/yandex-metrika.env
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

WM_API = "https://api.webmaster.yandex.net/v4"
MT_API = "https://api-metrika.yandex.net/management/v1"
APEX = "https://proverkastaza.ru"
HOST_ID = "https:proverkastaza.ru:443"
COUNTER_FALLBACK = "111134477"


def load_dotenv() -> None:
    root = Path(__file__).resolve().parents[1]
    for rel in ("secrets/yandex-webmaster.env", "secrets/yandex-metrika.env", ".env"):
        path = root / rel
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


def api(base: str, token: str, method: str, path: str, body: dict | None = None):
    headers = {"Authorization": f"OAuth {token}", "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return e.code, parsed


def main() -> int:
    load_dotenv()
    wt = os.environ.get("YANDEX_WEBMASTER_OAUTH_ACCESS_TOKEN", "").strip()
    mt = os.environ.get("YANDEX_METRIKA_OAUTH_ACCESS_TOKEN", "").strip()
    cid = (os.environ.get("YANDEX_METRIKA_COUNTER_ID") or COUNTER_FALLBACK).strip()
    if not wt.startswith("y0"):
        raise SystemExit("Нужен YANDEX_WEBMASTER_OAUTH_ACCESS_TOKEN")
    if not mt.startswith("y0"):
        raise SystemExit("Нужен YANDEX_METRIKA_OAUTH_ACCESS_TOKEN")

    code, user = api(WM_API, wt, "GET", "/user")
    if code != 200:
        raise SystemExit(f"webmaster /user {code}: {user}")
    uid = user["user_id"]
    enc = urllib.parse.quote(HOST_ID, safe="")

    print("=== API-доступно (делаем сами) ===")
    c, summary = api(WM_API, wt, "GET", f"/user/{uid}/hosts/{enc}/summary")
    print(f"apex summary [{c}]: searchable={summary.get('searchable_pages_count') if isinstance(summary, dict) else summary}")

    c, sm = api(WM_API, wt, "GET", f"/user/{uid}/hosts/{enc}/user-added-sitemaps")
    sms = (sm or {}).get("sitemaps") if isinstance(sm, dict) else []
    print(f"user-added sitemaps: {len(sms or [])}")
    if not sms:
        api(
            WM_API,
            wt,
            "POST",
            f"/user/{uid}/hosts/{enc}/user-added-sitemaps",
            {"url": f"{APEX}/wp-sitemap.xml"},
        )
        print("sitemap re-added")

    c, ctr = api(MT_API, mt, "GET", f"/counter/{cid}")
    if c != 200 or not isinstance(ctr, dict):
        raise SystemExit(f"metrika counter {c}: {ctr}")
    counter = ctr["counter"]
    print(
        f"metrika counter={counter.get('id')} status={counter.get('status')} "
        f"site={counter.get('site')} code_status={counter.get('code_status')}"
    )

    # Live site check
    with urllib.request.urlopen(APEX + "/", timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    print(f"live HTML has counter id: {cid in html}")

    print("\n=== API-недоступно (только UI Яндекса) ===")
    probe = api(
        WM_API,
        wt,
        "POST",
        f"/user/{uid}/hosts/{enc}/metrika/counters",
        {"counter_id": int(cid)},
    )
    print(f"POST .../metrika/counters -> {probe[0]} (ожидаем 404: метода нет в API v4)")

    c, diag = api(WM_API, wt, "GET", f"/user/{uid}/hosts/{enc}/diagnostics")
    problems = (diag or {}).get("problems") if isinstance(diag, dict) else {}
    for key in (
        "NO_METRIKA_COUNTER_BINDING",
        "NO_METRIKA_COUNTER_CRAWL_ENABLED",
        "NO_METRIKA_COUNTER",
    ):
        p = problems.get(key) or {}
        print(f"diagnostics {key}: state={p.get('state')}")

    print(
        f"""
=== Что нажать вручную (хост БЕЗ www) ===
1) Откройте apex, не www:
   https://webmaster.yandex.ru/site/{HOST_ID}/

2) Привязка счётчика {cid}:
   Настройки → Привязка к Яндекс Метрике → Добавить счётчик → {cid}
   (если вы владелец сайта и счётчика — подтвердится автоматически)

   Прямая страница настроек Метрики:
   https://metrika.yandex.ru/settings?id={cid}

3) Обход:
   Индексирование → Обход по счётчикам → включить рядом с {cid}

Счётчик на сайте уже стоит (consent-gated). Шаг «Создать счётчик» на www не нужен.
"""
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
