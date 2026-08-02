#!/usr/bin/env python3
"""Добавить A-запись supabase → staging IP через REG.API 2 (zone/add_alias).

Требует secrets/regru.env (см. secrets/regru.env.example).
IP вызывающей машины должен быть в allowlist API в кабинете Рег.ру.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "secrets" / "regru.env"
API = "https://api.reg.ru/api/regru2/zone/add_alias"
GET_RR = "https://api.reg.ru/api/regru2/zone/get_resource_records"


def _load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        raise SystemExit(
            f"Missing {path}. Copy docs/ops/regru.env.example → secrets/regru.env"
        )
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def _post(url: str, payload: dict) -> dict:
    body = urllib.parse.urlencode(
        {
            "input_format": "json",
            "output_content_type": "plain",
            "input_data": json.dumps(payload, ensure_ascii=False),
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code}: {raw[:500]}") from e
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise SystemExit(f"Non-JSON response: {raw[:500]}") from e


def main() -> None:
    env = _load_env(ENV_PATH)
    username = env.get("REGRU_USERNAME") or os.environ.get("REGRU_USERNAME")
    password = env.get("REGRU_PASSWORD") or os.environ.get("REGRU_PASSWORD")
    domain = env.get("REGRU_DOMAIN", "proverkastaza.ru")
    subdomain = env.get("REGRU_SUBDOMAIN", "supabase")
    ip = env.get("REGRU_IP", "51.250.13.240")
    if not username or not password:
        raise SystemExit("REGRU_USERNAME / REGRU_PASSWORD required in secrets/regru.env")

    existing = _post(
        GET_RR,
        {
            "username": username,
            "password": password,
            "domains": [{"dname": domain}],
        },
    )
    if existing.get("result") == "success":
        for d in existing.get("answer", {}).get("domains", []) or []:
            for rr in d.get("rrs", []) or []:
                if (
                    str(rr.get("subdomain", "")).lower() == subdomain.lower()
                    and str(rr.get("rectype", "")).upper() == "A"
                    and str(rr.get("content", "")) == ip
                ):
                    print(f"OK already present: {subdomain}.{domain} A {ip}")
                    return

    result = _post(
        API,
        {
            "username": username,
            "password": password,
            "domains": [{"dname": domain}],
            "subdomain": subdomain,
            "ipaddr": ip,
        },
    )
    if result.get("result") != "success":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit("FAIL zone/add_alias")
    print(f"OK added: {subdomain}.{domain} A {ip}")
    print("Next: nslookup supabase.proverkastaza.ru 8.8.8.8")
    print("Then wait for Caddy ACME (or restart caddy container on VM).")


if __name__ == "__main__":
    main()
