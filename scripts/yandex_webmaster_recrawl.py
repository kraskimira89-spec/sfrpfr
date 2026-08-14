#!/usr/bin/env python3
"""Переобход URL в Яндекс Вебмастере (после деплоя статей / смены зеркала).

Env: secrets/yandex-webmaster.env
  YANDEX_WEBMASTER_OAUTH_ACCESS_TOKEN
  YANDEX_WEBMASTER_SITE_URL=https://proverkastaza.ru
  YANDEX_WEBMASTER_HOST_ID=https:proverkastaza.ru:443  (опционально)

Usage:
  python scripts/yandex_webmaster_recrawl.py
  python scripts/yandex_webmaster_recrawl.py https://proverkastaza.ru/blog/...
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.webmaster.yandex.net/v4"

DEFAULT_URLS = (
    "https://proverkastaza.ru/",
    "https://proverkastaza.ru/proverka-stazha/",
    "https://proverkastaza.ru/proverka-stazha-pered-pensiey/",
    "https://proverkastaza.ru/proverka-severnogo-stazha/",
    "https://proverkastaza.ru/tarify/",
    "https://proverkastaza.ru/kak-rabotaem/",
    "https://proverkastaza.ru/kontakty/",
    "https://proverkastaza.ru/blog/",
    "https://proverkastaza.ru/wp-sitemap.xml",
    "https://proverkastaza.ru/blog/kak-zakazat-vypisku-ils/",
    "https://proverkastaza.ru/blog/kak-proverit-stazh-v-vypiske-ils/",
    "https://proverkastaza.ru/blog/kak-sverit-trudovuyu-knizhku-i-ils/",
    "https://proverkastaza.ru/blog/chto-delat-esli-period-raboty-ne-uchten/",
    "https://proverkastaza.ru/blog/chastye-voprosy-o-proverke-stazha/",
    "https://proverkastaza.ru/blog/arhivnaya-spravka-dlya-sfr-zachem-i-kuda/",
)


def load_dotenv() -> None:
    root = Path(__file__).resolve().parents[1]
    for rel in ("secrets/yandex-webmaster.env", ".env"):
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


def api(method: str, path: str, body: dict | None = None) -> tuple[int, dict | list | None]:
    token = os.environ.get("YANDEX_WEBMASTER_OAUTH_ACCESS_TOKEN", "").strip()
    if not token or not token.startswith("y0"):
        raise SystemExit("Нужен YANDEX_WEBMASTER_OAUTH_ACCESS_TOKEN вида y0_…")
    data = None
    headers = {"Authorization": f"OAuth {token}", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
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


def main() -> int:
    load_dotenv()
    code, user = api("GET", "/user")
    if code != 200 or not isinstance(user, dict):
        raise SystemExit(f"GET /user failed: {code} {user}")
    uid = user.get("user_id")
    host_id = os.environ.get("YANDEX_WEBMASTER_HOST_ID", "https:proverkastaza.ru:443").strip()
    host_q = urllib.parse.quote(host_id, safe="")

    urls = [u.strip() for u in sys.argv[1:] if u.strip()] or list(DEFAULT_URLS)
    print(f"user_id={uid} host_id={host_id}")
    for url in urls:
        code, out = api("POST", f"/user/{uid}/hosts/{host_q}/recrawl/queue", {"url": url})
        if code in (200, 202) and isinstance(out, dict):
            print(f"OK {url} task={out.get('task_id')} quota_left={out.get('quota_remainder')}")
            if out.get("quota_remainder") == 0:
                print("quota exhausted — stop")
                break
        elif code == 409:
            print(f"SKIP already queued: {url}")
        elif code == 429:
            print(f"QUOTA {url}: {out}")
            break
        else:
            print(f"WARN {code} {url}: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
