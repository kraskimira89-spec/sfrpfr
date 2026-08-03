"""Cutover dump Cloud → SQL (stable, column-filtered)."""
from __future__ import annotations

import re
import sys
from datetime import date, datetime, time
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "secrets" / "cutover-dumps" / "cloud_data.sql"
LOG = ROOT / "secrets" / "cutover-dumps" / "dump.log"

COPY_ORDER = [
    "auth.users",
    "auth.identities",
    "public.clients",
    "public.staff_roles",
    "public.cases",
    "public.case_representatives",
    "public.case_messages",
    "public.case_pipeline_data",
    "public.case_knowledge_feedback",
    "public.checklist_items",
    "public.documents",
    "public.communications",
    "public.consents",
    "public.contract_acceptances",
    "public.orders",
    "public.payments",
    "public.result_evidence",
    "public.access_audit",
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
        import json

        s = json.dumps(val, ensure_ascii=False).replace("'", "''")
        return f"'{s}'::jsonb"
    if isinstance(val, memoryview):
        val = bytes(val)
    if isinstance(val, (bytes, bytearray)):
        return r"'\x" + val.hex() + "'::bytea"
    s = str(val).replace("'", "''")
    return f"'{s}'"


def cloud_dsn() -> str:
    env = load_env(ROOT / ".env")
    dsn = env["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    dsn = re.sub(r":\d+/", ":6543/", dsn)
    dsn = re.sub(r"sslmode=[^&]*", "sslmode=require", dsn)
    if "sslmode=" not in dsn:
        dsn += ("&" if "?" in dsn else "?") + "sslmode=require"
    return dsn


def cols_for(cur, schema: str, table: str) -> list[str]:
    cur.execute(
        """
        select column_name
        from information_schema.columns
        where table_schema=%s and table_name=%s
          and is_generated = 'NEVER'
          and column_name not in ('confirmed_at')
        order by ordinal_position
        """,
        (schema, table),
    )
    return [r["column_name"] for r in cur.fetchall()]


def main() -> int:
    if LOG.exists():
        LOG.unlink()
    dsn = cloud_dsn()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    log("connect")
    conn = psycopg.connect(dsn, connect_timeout=45, row_factory=dict_row)
    parts = [
        "BEGIN;",
        "TRUNCATE TABLE public.clients CASCADE;",
        "TRUNCATE TABLE auth.refresh_tokens CASCADE;",
        "TRUNCATE TABLE auth.sessions CASCADE;",
        "TRUNCATE TABLE auth.identities CASCADE;",
        "TRUNCATE TABLE auth.users CASCADE;",
        "SET session_replication_role = replica;",
    ]
    with conn.cursor() as cur:
        for fq in COPY_ORDER:
            schema, table = fq.split(".", 1)
            cur.execute(
                """
                select 1 from information_schema.tables
                where table_schema=%s and table_name=%s
                """,
                (schema, table),
            )
            if not cur.fetchone():
                log(f"skip {fq}")
                continue
            cols = cols_for(cur, schema, table)
            if not cols:
                log(f"skip empty-cols {fq}")
                continue
            col_sql = ", ".join(f'"{c}"' for c in cols)
            log(f"fetch {fq} cols={len(cols)}")
            cur.execute(f'select {col_sql} from {schema}.{table}')
            rows = cur.fetchall()
            log(f"dump {fq} rows={len(rows)}")
            for row in rows:
                vals = ", ".join(sql_literal(row[c]) for c in cols)
                parts.append(
                    f'INSERT INTO {schema}.{table} ({col_sql}) VALUES ({vals});'
                )
    parts.append("SET session_replication_role = DEFAULT;")
    parts.append("COMMIT;")
    OUT.write_text("\n".join(parts) + "\n", encoding="utf-8")
    conn.close()
    log(f"OK bytes={OUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        log(f"FAIL {type(e).__name__}: {e}")
        raise
