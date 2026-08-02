#!/usr/bin/env python3
"""Сгенерировать секреты staging Supabase и записать в Lockbox (+ локальный secrets/).

Не коммитить вывод. Не трогает Yandex AI Studio / YANDEX_API_KEY.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

try:
    import jwt
except ImportError:
    sys.exit("pip install PyJWT")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "secrets" / "supabase-staging.env"
LOCKBOX_SUPABASE_ID = "e6qe9oa21ib1vpkkt0mh"
LOCKBOX_DATABASE_ID = "e6q1auj68j5u372c21ld"
YC = ROOT / "tools" / "yandex-cloud" / "bin" / "yc.exe"
if not YC.exists():
    YC = Path(os.environ.get("YC_PATH", r"C:\Users\user\yandex-cloud\bin\yc.exe"))


def _rand(n: int = 48) -> str:
    return secrets.token_urlsafe(n)


def _jwt(secret: str, role: str) -> str:
    now = int(time.time())
    payload = {
        "role": role,
        "iss": "supabase",
        "iat": now,
        "exp": now + 60 * 60 * 24 * 365 * 10,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _yc(*args: str) -> None:
    cmd = [str(YC), *args]
    env = os.environ.copy()
    env["YC_CLI_INITIALIZATION_SILENCE"] = "true"
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout or f"yc failed: {args}")


def main() -> None:
    jwt_secret = _rand(48)
    postgres_password = _rand(32)
    anon = _jwt(jwt_secret, "anon")
    service = _jwt(jwt_secret, "service_role")
    dashboard_password = _rand(24)
    secret_key_base = secrets.token_urlsafe(48)  # >= 64 chars typically
    while len(secret_key_base) < 64:
        secret_key_base += secrets.token_urlsafe(16)

    env_lines = {
        "POSTGRES_PASSWORD": postgres_password,
        "JWT_SECRET": jwt_secret,
        "ANON_KEY": anon,
        "SERVICE_ROLE_KEY": service,
        "DASHBOARD_USERNAME": "sfrfr",
        "DASHBOARD_PASSWORD": dashboard_password,
        "SECRET_KEY_BASE": secret_key_base,
        "API_EXTERNAL_URL": "https://supabase.proverkastaza.ru",
        "SUPABASE_PUBLIC_URL": "https://supabase.proverkastaza.ru",
        "SITE_URL": "https://cabinet.proverkastaza.ru",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "\n".join(f"{k}={v}" for k, v in env_lines.items()) + "\n",
        encoding="utf-8",
    )

    supabase_payload = json.dumps(
        [
            {"key": "JWT_SECRET", "text_value": jwt_secret},
            {"key": "ANON_KEY", "text_value": anon},
            {"key": "SERVICE_ROLE_KEY", "text_value": service},
            {"key": "DASHBOARD_USERNAME", "text_value": "sfrfr"},
            {"key": "DASHBOARD_PASSWORD", "text_value": dashboard_password},
            {"key": "SECRET_KEY_BASE", "text_value": secret_key_base},
            {"key": "API_EXTERNAL_URL", "text_value": env_lines["API_EXTERNAL_URL"]},
            {"key": "SUPABASE_PUBLIC_URL", "text_value": env_lines["SUPABASE_PUBLIC_URL"]},
            {"key": "SITE_URL", "text_value": env_lines["SITE_URL"]},
        ],
        ensure_ascii=False,
    )
    database_payload = json.dumps(
        [
            {"key": "POSTGRES_PASSWORD", "text_value": postgres_password},
            {
                "key": "DATABASE_URL",
                "text_value": (
                    f"postgresql://postgres:{postgres_password}@127.0.0.1:5432/postgres"
                ),
            },
        ],
        ensure_ascii=False,
    )

    _yc(
        "lockbox",
        "secret",
        "add-version",
        LOCKBOX_SUPABASE_ID,
        "--description",
        "staging supabase jwt/keys",
        "--payload",
        supabase_payload,
    )
    _yc(
        "lockbox",
        "secret",
        "add-version",
        LOCKBOX_DATABASE_ID,
        "--description",
        "staging postgres",
        "--payload",
        database_payload,
    )

    print("OK local=", OUT)
    print("OK lockbox supabase=", LOCKBOX_SUPABASE_ID)
    print("OK lockbox database=", LOCKBOX_DATABASE_ID)
    print("HINT: values not printed; open secrets/supabase-staging.env locally if needed")


if __name__ == "__main__":
    main()
