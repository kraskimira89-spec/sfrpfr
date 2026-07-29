#!/usr/bin/env python3
"""Создать/найти счётчик Яндекс Метрики и JS-цели lead_ok / max_click.

Требует env (или secrets/yandex-metrika.env):
  YANDEX_METRIKA_OAUTH_ACCESS_TOKEN
  YANDEX_METRIKA_SITE_URL=https://proverkastaza.ru
  YANDEX_METRIKA_COUNTER_NAME=Проверка стажа

Печатает строку YANDEX_METRIKA_COUNTER_ID=… для .env
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api-metrika.yandex.net/management/v1"
GOALS = (
    ("lead_ok", "Заявка отправлена (без ПДн)"),
    ("max_click", "Клик Открыть в MAX"),
)


def load_dotenv_files() -> None:
    root = Path(__file__).resolve().parents[1]
    for rel in ("secrets/yandex-metrika.env", ".env"):
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


def api(method: str, path: str, body: dict | None = None) -> dict:
    token = os.environ.get("YANDEX_METRIKA_OAUTH_ACCESS_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "Нет YANDEX_METRIKA_OAUTH_ACCESS_TOKEN. См. docs/ops/yandex-metrika-setup.md"
        )
    url = f"{API}{path}"
    data = None
    headers = {
        "Authorization": f"OAuth {token}",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code} {method} {path}\n{err}") from e


def site_host() -> str:
    raw = os.environ.get("YANDEX_METRIKA_SITE_URL", "https://proverkastaza.ru").strip()
    host = urllib.parse.urlparse(raw if "://" in raw else f"https://{raw}").hostname
    if not host:
        raise SystemExit("Некорректный YANDEX_METRIKA_SITE_URL")
    return host.lower()


def find_counter(host: str) -> dict | None:
    data = api("GET", "/counters")
    for c in data.get("counters") or []:
        site = (c.get("site") or "").lower()
        site2 = ((c.get("site2") or {}).get("site") or "").lower()
        if host in (site, site2) or site.endswith(host) or host in site:
            return c
        mirrors = c.get("mirrors2") or c.get("mirrors") or []
        for m in mirrors:
            msite = (m.get("site") if isinstance(m, dict) else str(m) or "").lower()
            if host in msite or msite == host:
                return c
    return None


def create_counter(host: str) -> dict:
    name = os.environ.get("YANDEX_METRIKA_COUNTER_NAME", "Проверка стажа").strip()
    body = {
        "counter": {
            "name": name,
            "site": host,
            "site2": {"site": host},
            "gdpr_agreement_accepted": True,
            "webvisor": {"urls": "", "arch_enabled": 0, "arch_type": "html"},
            "code_options": {
                "async": 1,
                "informer": {"enabled": 0},
                "visor": 0,
                "track_hash": 1,
                "xml_site": 0,
                "clickmap": 1,
                "ecommerce": 0,
            },
        }
    }
    return api("POST", "/counters", body)


def list_goals(counter_id: int) -> list[dict]:
    data = api("GET", f"/counter/{counter_id}/goals")
    return list(data.get("goals") or [])


def ensure_action_goal(counter_id: int, ident: str, title: str, existing: list[dict]) -> None:
    for g in existing:
        conds = g.get("conditions") or []
        for cond in conds:
            if (cond.get("url") or "") == ident:
                print(f"  goal ok: {ident} (id={g.get('id')})")
                return
        if (g.get("name") or "") == title or (g.get("name") or "") == ident:
            print(f"  goal ok by name: {ident} (id={g.get('id')})")
            return
    body = {
        "goal": {
            "name": title,
            "type": "action",
            "is_retargeting": 0,
            "conditions": [{"type": "exact", "url": ident}],
        }
    }
    out = api("POST", f"/counter/{counter_id}/goals", body)
    gid = (out.get("goal") or {}).get("id")
    print(f"  goal created: {ident} (id={gid})")


def main() -> int:
    load_dotenv_files()
    host = site_host()
    print(f"site={host}")
    counter = find_counter(host)
    if counter:
        print(f"found counter id={counter.get('id')} name={counter.get('name')!r}")
    else:
        print("creating counter…")
        created = create_counter(host)
        counter = created.get("counter") or created
        print(f"created counter id={counter.get('id')}")

    cid = int(counter["id"])
    goals = list_goals(cid)
    print("goals:")
    for ident, title in GOALS:
        ensure_action_goal(cid, ident, title, goals)
        goals = list_goals(cid)

    print()
    print(f"YANDEX_METRIKA_COUNTER_ID={cid}")
    print("Добавьте эту строку в secrets/yandex-metrika.env и /opt/sfrfr/.env")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
