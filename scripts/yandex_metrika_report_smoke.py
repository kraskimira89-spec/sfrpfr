#!/usr/bin/env python3
"""Smoke-проверка Reports API Метрики (агрегаты, без logs/ПДн).

Env: secrets/yandex-metrika.env
  YANDEX_METRIKA_OAUTH_ACCESS_TOKEN
  YANDEX_METRIKA_COUNTER_ID=111134477
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

STAT = "https://api-metrika.yandex.net/stat/v1/data"
MGMT = "https://api-metrika.yandex.net/management/v1"


def load_dotenv() -> None:
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


def get(url: str) -> dict:
    token = os.environ.get("YANDEX_METRIKA_OAUTH_ACCESS_TOKEN", "").strip()
    if not token:
        raise SystemExit("Нет YANDEX_METRIKA_OAUTH_ACCESS_TOKEN")
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"OAuth {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}") from e


def main() -> int:
    load_dotenv()
    cid = os.environ.get("YANDEX_METRIKA_COUNTER_ID", "").strip() or "111134477"
    print(f"counter_id={cid}")

    counter = get(f"{MGMT}/counter/{cid}").get("counter") or {}
    print(
        "mgmt:",
        f"filter_robots={counter.get('filter_robots')}",
        f"visor={(counter.get('code_options') or {}).get('visor')}",
        f"code_status={counter.get('code_status')}",
    )
    goals = get(f"{MGMT}/counter/{cid}/goals").get("goals") or []
    idents = []
    for g in goals:
        for c in g.get("conditions") or []:
            if c.get("url"):
                idents.append(c["url"])
    print("goals:", ", ".join(idents) or "(none)")

    q = urllib.parse.urlencode(
        {
            "ids": cid,
            "metrics": "ym:s:visits,ym:s:users,ym:s:pageviews",
            "date1": "7daysAgo",
            "date2": "today",
        }
    )
    data = get(f"{STAT}?{q}")
    totals = data.get("totals") or []
    print("reports_7d totals visits/users/pageviews:", totals)

    q2 = urllib.parse.urlencode(
        {
            "ids": cid,
            "metrics": "ym:s:sumGoalReachesAny",
            "date1": "30daysAgo",
            "date2": "today",
        }
    )
    try:
        goals_rep = get(f"{STAT}?{q2}")
        print("sumGoalReachesAny_30d:", (goals_rep.get("totals") or [None])[0])
    except SystemExit as e:
        # fallback: per-goal reaches by id
        print(f"WARN sumGoalReachesAny unavailable: {e}")
        for g in goals[:6]:
            gid = g.get("id")
            if not gid:
                continue
            qg = urllib.parse.urlencode(
                {
                    "ids": cid,
                    "metrics": f"ym:s:goal{gid}reaches",
                    "date1": "30daysAgo",
                    "date2": "today",
                }
            )
            try:
                one = get(f"{STAT}?{qg}")
                print(f"  goal_id={gid} reaches={(one.get('totals') or [None])[0]}")
            except SystemExit as e2:
                print(f"  goal_id={gid} WARN {e2}")

    # CS_ERR_UNKNOWN нормален при загрузке счётчика только после согласия.
    if counter.get("code_status") not in (None, "CS_OK", "CS_ERR_UNKNOWN", "CS_NOT_FOUND"):
        print(f"WARN unusual code_status={counter.get('code_status')}")
    print("OK smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
