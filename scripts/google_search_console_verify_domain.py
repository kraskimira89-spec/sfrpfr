#!/usr/bin/env python3
"""Подтверждение proverkastaza.ru в Google Search Console через API.

Пути:
  A) Domain (DNS TXT) — Site Verification API + TXT в reg.ru (secrets/regru.env)
  B) URL-prefix (META) — Site Verification API + meta в WP MU-плагине

Блокеры (разово вручную):
  1) Включить API:
     https://console.developers.google.com/apis/api/siteverification.googleapis.com/overview?project=sfrfr-sheets
  2) Для DNS: secrets/regru.env (REGRU_USERNAME / REGRU_PASSWORD)

Запуск:
  set PYTHONPATH=src
  python scripts/google_search_console_verify_domain.py
  python scripts/google_search_console_verify_domain.py --method meta
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sfrfr.integrations.google_sa import access_token, load_service_account_info  # noqa: E402

DOMAIN = "proverkastaza.ru"
SITE_URL = "https://proverkastaza.ru/"
SC_DOMAIN = f"sc-domain:{DOMAIN}"
GSC_JSON = ROOT / "secrets" / "sfrfr-sheets-Google-Search-Console-06b255b04ddd.json"
REGRU_ENV = ROOT / "secrets" / "regru.env"
META_CFG = ROOT / "scripts" / "wp-mu-plugins" / "sfrfr-google-verification.config.php"
ENABLE_API_URL = (
    "https://console.developers.google.com/apis/api/"
    "siteverification.googleapis.com/overview?project=sfrfr-sheets"
)

SCOPES = [
    "https://www.googleapis.com/auth/siteverification",
    "https://www.googleapis.com/auth/webmasters",
]


def _load_regru() -> dict[str, str]:
    data: dict[str, str] = {}
    if not REGRU_ENV.is_file():
        return data
    for line in REGRU_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def _regru_post(url: str, payload: dict) -> dict:
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
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _http_json(method: str, url: str, token: str, payload: dict | None = None) -> tuple[int, dict | str]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def get_token_meta(token: str) -> str:
    code, body = _http_json(
        "POST",
        "https://www.googleapis.com/siteVerification/v1/token",
        token,
        {
            "site": {"type": "SITE", "identifier": SITE_URL},
            "verificationMethod": "META",
        },
    )
    if code >= 400:
        raise SystemExit(f"META token failed {code}: {body}")
    assert isinstance(body, dict)
    return str(body.get("token") or "")


def get_token_dns(token: str) -> str:
    code, body = _http_json(
        "POST",
        "https://www.googleapis.com/siteVerification/v1/token",
        token,
        {
            "site": {"type": "INET_DOMAIN", "identifier": DOMAIN},
            "verificationMethod": "DNS_TXT",
        },
    )
    if code >= 400:
        raise SystemExit(f"DNS token failed {code}: {body}")
    assert isinstance(body, dict)
    return str(body.get("token") or "")


def write_meta_config(meta_content: str) -> None:
    # meta looks like: <meta name="google-site-verification" content="TOKEN" />
    import re

    m = re.search(r'content="([^"]+)"', meta_content)
    ver = m.group(1) if m else meta_content.strip()
    META_CFG.write_text(
        "<?php\n"
        "/** Автоген: scripts/google_search_console_verify_domain.py */\n"
        f"return '{ver}';\n",
        encoding="utf-8",
    )
    print(f"Wrote {META_CFG} content={ver[:16]}…")


def add_dns_txt(txt_value: str) -> None:
    env = _load_regru()
    username = env.get("REGRU_USERNAME") or os.environ.get("REGRU_USERNAME")
    password = env.get("REGRU_PASSWORD") or os.environ.get("REGRU_PASSWORD")
    domain = env.get("REGRU_DOMAIN", DOMAIN)
    if not username or not password:
        raise SystemExit(
            "Нет secrets/regru.env — добавьте TXT вручную в reg.ru:\n"
            f"  Host: @\n  Type: TXT\n  Value: {txt_value}"
        )
    existing = _regru_post(
        "https://api.reg.ru/api/regru2/zone/get_resource_records",
        {"username": username, "password": password, "domains": [{"dname": domain}]},
    )
    records = (
        (((existing.get("answer") or {}).get("domains") or [{}])[0].get("rrs")) or []
    )
    for rr in records:
        if str(rr.get("rectype") or "").upper() == "TXT" and txt_value in str(
            rr.get("content") or rr.get("textdata") or ""
        ):
            print("TXT already present in reg.ru")
            return
    # REG.API: zone/add_txt
    added = _regru_post(
        "https://api.reg.ru/api/regru2/zone/add_txt",
        {
            "username": username,
            "password": password,
            "domains": [{"dname": domain}],
            "subdomain": "@",
            "text": txt_value,
        },
    )
    print("reg.ru add_txt:", json.dumps(added, ensure_ascii=False)[:500])
    if added.get("result") != "success":
        raise SystemExit(f"reg.ru failed: {added}")


def verify_site(token: str, *, method: str) -> None:
    if method == "meta":
        payload = {"site": {"type": "SITE", "identifier": SITE_URL}}
        url = (
            "https://www.googleapis.com/siteVerification/v1/webResource"
            "?verificationMethod=META"
        )
    else:
        payload = {"site": {"type": "INET_DOMAIN", "identifier": DOMAIN}}
        url = (
            "https://www.googleapis.com/siteVerification/v1/webResource"
            "?verificationMethod=DNS_TXT"
        )
    last: dict | str = {}
    for attempt in range(1, 9):
        code, body = _http_json("POST", url, token, payload)
        last = body
        print(f"verify attempt {attempt}: {code}")
        if code < 400:
            print("Verified:", json.dumps(body, ensure_ascii=False)[:400])
            return
        time.sleep(8)
    raise SystemExit(f"Verify failed: {last}")


def add_gsc_property(token: str, site_url: str) -> None:
    encoded = urllib.parse.quote(site_url, safe="")
    code, body = _http_json(
        "PUT",
        f"https://www.googleapis.com/webmasters/v3/sites/{encoded}",
        token,
        None,
    )
    print(f"GSC add {site_url}: {code} {body}")
    if code >= 400 and code != 409:
        raise SystemExit(f"GSC add failed: {body}")


def list_gsc(token: str) -> None:
    code, body = _http_json(
        "GET",
        "https://www.googleapis.com/webmasters/v3/sites",
        token,
        None,
    )
    print("GSC sites:", code, json.dumps(body, ensure_ascii=False)[:800])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--method",
        choices=("dns", "meta"),
        default="dns",
        help="dns = Domain property; meta = URL-prefix https://…/",
    )
    args = parser.parse_args()

    if not GSC_JSON.is_file():
        raise SystemExit(f"Missing {GSC_JSON}")

    info = load_service_account_info(
        str(GSC_JSON),
        env_name="GOOGLE_SEARCH_CONSOLE_CREDENTIALS_JSON",
    )
    print("SA:", info.get("client_email"))
    token = access_token(info, scopes=SCOPES)

    # Probe API
    code, body = _http_json(
        "POST",
        "https://www.googleapis.com/siteVerification/v1/token",
        token,
        {
            "site": {"type": "SITE", "identifier": SITE_URL},
            "verificationMethod": "META",
        },
    )
    if code == 403 and isinstance(body, dict) and "has not been used" in str(body):
        raise SystemExit(
            "Site Verification API выключен в проекте sfrfr-sheets.\n"
            f"Откройте и включите (владелец GCP):\n  {ENABLE_API_URL}\n"
            "Затем снова: python scripts/google_search_console_verify_domain.py"
        )
    if code >= 400:
        raise SystemExit(f"API probe failed {code}: {body}")

    if args.method == "meta":
        meta = get_token_meta(token)
        print("META token HTML:", meta)
        write_meta_config(meta)
        print(
            "Задеплойте на VPS:\n"
            "  scp scripts/wp-mu-plugins/sfrfr-google-verification* "
            "root@VPS:/var/www/.../mu-plugins/\n"
            "Затем: wp cache flush && перезапустите скрипт "
            "(verify уже вызывается ниже — meta должен быть на сайте)."
        )
        verify_site(token, method="meta")
        add_gsc_property(token, SITE_URL)
    else:
        txt = get_token_dns(token)
        print("DNS TXT value:", txt)
        try:
            add_dns_txt(txt)
        except SystemExit as e:
            print(str(e))
            print("После добавления TXT вручную перезапустите скрипт с --method dns")
            raise
        print("Ждём распространения DNS…")
        time.sleep(15)
        verify_site(token, method="dns")
        add_gsc_property(token, SC_DOMAIN)
        add_gsc_property(token, SITE_URL)

    list_gsc(token)
    print("OK")


if __name__ == "__main__":
    main()
