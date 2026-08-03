#!/usr/bin/env python3
"""Cutover helper: dump Cloud public+auth data → import on YC self-host, print switch checklist.

Does NOT change VPS env by itself. Secrets stay local.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
STAGING = ROOT / "secrets" / "supabase-staging.env"
DUMP_DIR = ROOT / "secrets" / "cutover-dumps"
CA = ROOT / "secrets" / "prod-ca-2021.crt"


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def to_psycopg_dsn(raw: str) -> str:
    dsn = raw.replace("postgresql+psycopg://", "postgresql://")
    # pg_dump prefers sslrootcert file for verify-full
    return dsn


def mask(dsn: str) -> str:
    return re.sub(r":([^:@/]+)@", ":***@", dsn)


def main() -> int:
    cloud = load_env(ENV)
    staging = load_env(STAGING)
    raw = cloud.get("DATABASE_URL") or ""
    if not raw:
        print("FAIL: DATABASE_URL missing in .env", file=sys.stderr)
        return 1
    dsn = to_psycopg_dsn(raw)
    print("cloud_dsn", mask(dsn))
    print("target_api", staging.get("API_EXTERNAL_URL"))

    DUMP_DIR.mkdir(parents=True, exist_ok=True)
    dump_sql = DUMP_DIR / "cloud_public_auth_data.sql"

    env = os.environ.copy()
    if CA.is_file():
        env["PGSSLROOTCERT"] = str(CA)

    # Prefer dockerized pg_dump (available via staging VM later). Local try first.
    cmd = [
        "pg_dump",
        dsn,
        "--data-only",
        "--no-owner",
        "--no-privileges",
        "--disable-triggers",
        "-n",
        "public",
        "-n",
        "auth",
        "-f",
        str(dump_sql),
    ]
    print("RUN", " ".join(cmd[:2] + ["***"] + cmd[3:]))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    except FileNotFoundError:
        print("pg_dump not found locally; will use docker on YC VM path")
        dump_meta = DUMP_DIR / "cloud_dsn.url"
        # store only for local cutover; gitignored under secrets/
        dump_meta.write_text(dsn + "\n", encoding="utf-8")
        print("WROTE", dump_meta)
        return 2

    if r.returncode != 0:
        print(r.stderr[-2000:], file=sys.stderr)
        dump_meta = DUMP_DIR / "cloud_dsn.url"
        dump_meta.write_text(dsn + "\n", encoding="utf-8")
        print("FALLBACK wrote", dump_meta)
        return 2

    print("OK dump", dump_sql, "bytes", dump_sql.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
