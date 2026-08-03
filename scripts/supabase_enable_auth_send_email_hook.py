#!/usr/bin/env python3
"""Включить Auth Send Email Hook → API SFRFR (Яндекс-почта РФ).

Нужен Personal Access Token в secrets/supabase-access.env:
  SUPABASE_ACCESS_TOKEN=sbp_...
  SUPABASE_PROJECT_REF=frualvycousvvyjivybu

Секрет хука (Standard Webhooks):
  SUPABASE_SEND_EMAIL_HOOK_SECRET=v1,whsec_...
Если не задан — генерируется и печатается (добавьте в /opt/sfrfr/.env и .env).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / "secrets" / "supabase-access.env"
DEFAULT_REF = "frualvycousvvyjivybu"
DEFAULT_URI = "https://api.proverkastaza.ru/api/integrations/supabase/auth-send-email"


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def _gen_secret() -> str:
    raw = secrets.token_bytes(32)
    return "v1,whsec_" + base64.b64encode(raw).decode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description="Enable Supabase Auth Send Email Hook")
    parser.add_argument("--uri", default=DEFAULT_URI, help="HTTPS endpoint URL")
    parser.add_argument(
        "--secret",
        default="",
        help="v1,whsec_... (иначе из env или сгенерировать)",
    )
    parser.add_argument(
        "--disable",
        action="store_true",
        help="Выключить хук (вернуть встроенный mailer Supabase)",
    )
    args = parser.parse_args()

    _load_dotenv(SECRETS)
    _load_dotenv(ROOT / ".env")
    token = (os.environ.get("SUPABASE_ACCESS_TOKEN") or "").strip()
    ref = (os.environ.get("SUPABASE_PROJECT_REF") or DEFAULT_REF).strip()
    if not token:
        print(
            "Нет SUPABASE_ACCESS_TOKEN в secrets/supabase-access.env",
            file=sys.stderr,
        )
        return 2

    if args.disable:
        payload = {
            "hook_send_email_enabled": False,
            "hook_send_email_uri": "",
            "hook_send_email_secrets": "",
        }
    else:
        secret = (args.secret or os.environ.get("SUPABASE_SEND_EMAIL_HOOK_SECRET") or "").strip()
        generated = False
        if not secret:
            secret = _gen_secret()
            generated = True
        if not secret.startswith("v1,"):
            secret = "v1," + secret.removeprefix("v1,")
        payload = {
            "hook_send_email_enabled": True,
            "hook_send_email_uri": args.uri.strip(),
            "hook_send_email_secrets": secret,
        }
        print("HOOK_URI=", args.uri.strip())
        if generated:
            print("GENERATED_SECRET (добавьте в .env и /opt/sfrfr/.env):")
            print(f"SUPABASE_SEND_EMAIL_HOOK_SECRET={secret}")
        else:
            print("Используем секрет из --secret / env (не печатаем)")

    url = f"https://api.supabase.com/v1/projects/{ref}/config/auth"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "sfrfr-ops/1.0",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            print(f"OK HTTP {resp.status}: Auth Send Email Hook updated (project={ref})")
            print("enabled=", payload.get("hook_send_email_enabled"))
            return 0
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {err[:800]}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
