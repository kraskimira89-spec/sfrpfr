"""Сбор открытых задач Tracker (без ПДн) + сводка в JSON."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "secrets" / "yandex-tracker.env"


def _load_env() -> None:
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    _load_env()
    sys.path.insert(0, str(ROOT / "src"))
    import httpx
    from sfrfr.integrations.yandex_tracker import API_BASE, _headers

    queues = ["STAZH", "SFRFR", "PUB", "FUNNEL"]
    closed = {
        "closed",
        "resolved",
        "done",
        "cancelled",
        "canceled",
        "отменен",
        "отменён",
        "решен",
        "решён",
        "закрыт",
    }
    out: dict = {}
    with httpx.Client(timeout=45.0) as client:
        for q in queues:
            r = client.post(
                f"{API_BASE}/issues/_search",
                headers=_headers(),
                json={"query": f'Queue: {q}', "perPage": 100},
            )
            raw = r.json() if r.content else []
            issues = []
            if isinstance(raw, list):
                for i in raw:
                    st = i.get("status") or {}
                    sk = str(st.get("key") or "").lower()
                    sd = str(st.get("display") or "").lower()
                    if sk in closed or sd in closed:
                        continue
                    if "закрыт" in sd or "реш" in sd or "отмен" in sd:
                        continue
                    issues.append(
                        {
                            "key": i.get("key"),
                            "summary": i.get("summary"),
                            "status": st.get("display") or st.get("key"),
                            "priority": (i.get("priority") or {}).get("display")
                            or (i.get("priority") or {}).get("key"),
                            "tags": i.get("tags") or [],
                        }
                    )
            out[q] = {
                "http": r.status_code,
                "open_n": len(issues),
                "issues": issues,
            }
    path = ROOT / "docs" / "ops" / "tech-debt-tracker-snapshot.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v["open_n"] for k, v in out.items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
