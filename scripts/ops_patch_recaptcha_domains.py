#!/usr/bin/env python3
"""Добавить домены витрины в allowlist reCAPTCHA Enterprise key (webSettings.allowedDomains)."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from google.auth.transport.requests import Request
from google.oauth2 import service_account

PROJECT = os.environ.get("RECAPTCHA_PROJECT_ID", "sfrfr-sheets")
SITE_KEY = os.environ.get(
    "RECAPTCHA_SITE_KEY", "6Lf7UWMtAAAAANDXkb8MR9ufU8QYO9UwZsEC3NHu"
)
CREDS = os.environ.get(
    "RECAPTCHA_CREDENTIALS_JSON",
    "secrets/sfrfr-sheets-reCAPTCHA-Enterprise-ac8f4d954b9a.json",
)
ADD_DOMAINS = [
    "proverkastaza.ru",
    "www.proverkastaza.ru",
    "prostaz.ru",
    "www.prostaz.ru",
    "proverka-staza.ru",
    "www.proverka-staza.ru",
]


def main() -> int:
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    creds = service_account.Credentials.from_service_account_file(CREDS, scopes=scopes)
    creds.refresh(Request())
    key_name = f"projects/{PROJECT}/keys/{SITE_KEY}"
    base = f"https://recaptchaenterprise.googleapis.com/v1/{key_name}"
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(base, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        print("GET_FAIL", e.code, e.read().decode()[:2000], file=sys.stderr)
        return 1

    web = data.get("webSettings") or {}
    current = list(web.get("allowedDomains") or [])
    print("current_domains:", current)

    merged = sorted(set(current) | set(ADD_DOMAINS))
    if merged == sorted(set(current)):
        print("OK: domains already present")
        return 0

    body = json.dumps({"webSettings": {"allowedDomains": merged}}).encode()
    patch_url = f"{base}?updateMask=webSettings.allowedDomains"
    req = urllib.request.Request(patch_url, data=body, headers=headers, method="PATCH")
    try:
        with urllib.request.urlopen(req) as resp:
            out = json.load(resp)
    except urllib.error.HTTPError as e:
        print("PATCH_FAIL", e.code, e.read().decode()[:2000], file=sys.stderr)
        return 1

    print("updated_domains:", (out.get("webSettings") or {}).get("allowedDomains"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
