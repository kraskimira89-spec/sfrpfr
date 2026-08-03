"""Dump Cloud public tables via REST + auth.users via short DB COPY."""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime, time
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "secrets" / "cutover-dumps" / "cloud_data.sql"
LOG = ROOT / "secrets" / "cutover-dumps" / "dump.log"

PUBLIC_TABLES = [
    "clients",
    "staff_roles",
    "cases",
    "case_representatives",
    "case_messages",
    "case_pipeline_data",
    "case_knowledge_feedback",
    "checklist_items",
    "documents",
    "communications",
    "consents",
    "contract_acceptances",
    "orders",
    "payments",
    "result_evidence",
    "access_audit",
]


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def sql_literal(val) -> str:
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, UUID):
        return f"'{val}'::uuid"
    if isinstance(val, datetime):
        return f"'{val.isoformat()}'::timestamptz"
    if isinstance(val, date):
        return f"'{val.isoformat()}'::date"
    if isinstance(val, time):
        return f"'{val.isoformat()}'::time"
    if isinstance(val, (dict, list)):
        s = json.dumps(val, ensure_ascii=False).replace("'", "''")
        return f"'{s}'::jsonb"
    if isinstance(val, (bytes, bytearray, memoryview)):
        return r"'\x" + bytes(val).hex() + "'::bytea"
    s = str(val).replace("'", "''")
    if len(s) == 36 and s.count("-") == 4:
        return f"'{s}'::uuid"
    if "T" in s and ("+" in s or s.endswith("Z") or s.count("-") >= 2):
        try:
            datetime.fromisoformat(s.replace("Z", "+00:00"))
            return f"'{s}'::timestamptz"
        except ValueError:
            pass
    return f"'{s}'"


def insert_rows(schema: str, table: str, rows: list[dict], skip: set[str] | None = None) -> list[str]:
    if not rows:
        return []
    skip = skip or set()
    cols = [c for c in rows[0].keys() if c not in skip]
    col_sql = ", ".join(f'"{c}"' for c in cols)
    out = []
    for row in rows:
        vals = ", ".join(sql_literal(row.get(c)) for c in cols)
        out.append(f'INSERT INTO {schema}.{table} ({col_sql}) VALUES ({vals});')
    return out


def db_dsn(env: dict[str, str]) -> str:
    dsn = env["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    dsn = re.sub(r":\d+/", ":5432/", dsn)
    dsn = re.sub(r"sslmode=[^&]*", "sslmode=require", dsn)
    if "sslmode=" not in dsn:
        dsn += ("&" if "?" in dsn else "?") + "sslmode=require"
    return dsn


def dump_auth_via_db(dsn: str) -> list[str]:
    """COPY auth.users/identities — сохраняет encrypted_password."""
    out: list[str] = []
    for table in ("users", "identities"):
        log(f"db auth.{table}")
        with psycopg.connect(dsn, connect_timeout=30, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("set statement_timeout='30s'")
                cur.execute(
                    """
                    select column_name from information_schema.columns
                    where table_schema='auth' and table_name=%s and is_generated='NEVER'
                    order by ordinal_position
                    """,
                    (table,),
                )
                cols = [r["column_name"] for r in cur.fetchall()]
                col_sql = ", ".join(f'"{c}"' for c in cols)
                cur.execute(f"select {col_sql} from auth.{table}")
                rows = cur.fetchall()
                log(f"dump auth.{table} rows={len(rows)}")
                out.extend(insert_rows("auth", table, rows, skip={"confirmed_at"}))
    return out


def main() -> int:
    if LOG.exists():
        LOG.unlink()
    # Cloud keys: prefer env CLOUD_* fallbacks, else VPS-style if URL is supabase.co
    env = load_env(ROOT / ".env")
    cloud_url = (
        os.environ.get("CLOUD_SUPABASE_URL")
        or env.get("CLOUD_SUPABASE_URL")
        or ""
    ).rstrip("/")
    cloud_key = os.environ.get("CLOUD_SUPABASE_SERVICE_ROLE_KEY") or env.get(
        "CLOUD_SUPABASE_SERVICE_ROLE_KEY", ""
    )
    if not cloud_url or "supabase.co" not in cloud_url:
        # DATABASE_URL still points to Cloud pooler — public via REST needs cloud URL/key from VPS file optional
        vps_env = Path("/opt/sfrfr/.env")
        if vps_env.is_file():
            ve = load_env(vps_env)
            cloud_url = ve.get("SUPABASE_URL", "").rstrip("/")
            cloud_key = ve.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not cloud_url or "supabase.co" not in cloud_url:
        log("FAIL: set CLOUD_SUPABASE_URL + CLOUD_SUPABASE_SERVICE_ROLE_KEY (Cloud)")
        return 1

    log(f"cloud_api={cloud_url}")
    client = create_client(cloud_url, cloud_key)
    dsn = db_dsn(env)

    parts = [
        "BEGIN;",
        "TRUNCATE TABLE public.clients CASCADE;",
        "TRUNCATE TABLE auth.refresh_tokens CASCADE;",
        "TRUNCATE TABLE auth.sessions CASCADE;",
        "TRUNCATE TABLE auth.identities CASCADE;",
        "TRUNCATE TABLE auth.users CASCADE;",
        "SET session_replication_role = replica;",
    ]

    try:
        parts.extend(dump_auth_via_db(dsn))
    except Exception as e:
        log(f"WARN auth db dump: {type(e).__name__}: {e} — magic-link only users")

    for table in PUBLIC_TABLES:
        log(f"rest public.{table}")
        try:
            res = client.table(table).select("*").execute()
            rows = res.data or []
            log(f"dump public.{table} rows={len(rows)}")
            parts.extend(insert_rows("public", table, rows))
        except Exception as e:
            log(f"WARN public.{table}: {type(e).__name__}: {e}")

    parts.append("SET session_replication_role = DEFAULT;")
    parts.append("COMMIT;")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts) + "\n", encoding="utf-8")
    log(f"OK bytes={OUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        log(f"FAIL {type(e).__name__}: {e}")
        raise
