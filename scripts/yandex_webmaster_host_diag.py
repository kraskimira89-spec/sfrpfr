#!/usr/bin/env python3
"""Диагностика хостов Вебмастера: www vs apex, индекс, sitemap."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.webmaster.yandex.net/v4"


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


def api(path: str):
    token = os.environ["YANDEX_WEBMASTER_OAUTH_ACCESS_TOKEN"].strip()
    req = urllib.request.Request(
        API + path,
        headers={"Authorization": f"OAuth {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode() or "null")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw}
        return e.code, body


def main() -> None:
    load_dotenv()
    code, user = api("/user")
    if code != 200:
        raise SystemExit(f"user {code}: {user}")
    uid = user["user_id"]
    print(f"user_id={uid}")
    code, hosts = api(f"/user/{uid}/hosts")
    if code != 200:
        raise SystemExit(f"hosts {code}: {hosts}")
    for h in hosts.get("hosts") or []:
        hid = h["host_id"]
        enc = urllib.parse.quote(hid, safe="")
        print("\n==== HOST ====")
        print(json.dumps(h, ensure_ascii=False, indent=2))
        for ep in (
            "summary",
            "indexing/hosts-history",
            "indexing/samples",
            "search-urls/events/history",
            "search-urls/events/samples",
            "sitemaps",
            "user-added-sitemaps",
        ):
            c, data = api(f"/user/{uid}/hosts/{enc}/{ep}")
            preview = json.dumps(data, ensure_ascii=False)
            if len(preview) > 800:
                preview = preview[:800] + "…"
            print(f"\n[{c}] {ep}: {preview}")


if __name__ == "__main__":
    main()
