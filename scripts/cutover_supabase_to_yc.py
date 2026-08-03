#!/usr/bin/env python3
"""Миграция данных Cloud → self-host YC + печать значений для переключения env.

Требует: локальный доступ к Cloud DATABASE_URL; SSH tunnel к staging Postgres
  ssh -N -L 55432:127.0.0.1:5432 sfrfr@51.250.13.240

Не печатает секреты. Не меняет VPS сам.
"""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


PUBLIC_TABLES = [
    "clients",
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
    "staff_roles",
]

# order for FK-safe truncate/copy
PUBLIC_ORDER = list(reversed(PUBLIC_TABLES))  # truncate children first... actually truncate CASCADE
COPY_ORDER = [
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


def count_table(conn: psycopg.Connection, schema: str, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("select count(*) from {}.{}").format(
                sql.Identifier(schema), sql.Identifier(table)
            )
        )
        return int(cur.fetchone()[0])


def table_exists(conn: psycopg.Connection, schema: str, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            select 1 from information_schema.tables
            where table_schema=%s and table_name=%s
            """,
            (schema, table),
        )
        return cur.fetchone() is not None


def copy_table(
    src: psycopg.Connection, dst: psycopg.Connection, schema: str, table: str
) -> int:
    fq = f"{schema}.{table}"
    with src.cursor() as sc, dst.cursor() as dc:
        with sc.copy(f"COPY {fq} TO STDOUT") as copy_out:
            data = copy_out.read()
        if not data:
            return 0
        with dc.copy(f"COPY {fq} FROM STDIN") as copy_in:
            copy_in.write(data)
    return data.count(b"\n")


def main() -> int:
    cloud_env = load_env(ROOT / ".env")
    st_env = load_env(ROOT / "secrets" / "supabase-staging.env")
    cloud_dsn = cloud_env["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    # staging via local tunnel
    st_pass = st_env["POSTGRES_PASSWORD"]
    st_dsn = (
        f"postgresql://postgres:{st_pass}@127.0.0.1:55432/postgres"
        f"?sslmode=disable"
    )

    ca = ROOT / "secrets" / "prod-ca-2021.crt"
    connect_kwargs = {}
    if ca.is_file() and "sslrootcert" not in cloud_dsn:
        sep = "&" if "?" in cloud_dsn else "?"
        cloud_dsn = f"{cloud_dsn}{sep}sslrootcert={ca.as_posix()}"

    print("Connecting cloud...")
    src = psycopg.connect(cloud_dsn, connect_timeout=30)
    print("Connecting staging via tunnel :55432 ...")
    dst = psycopg.connect(st_dsn, connect_timeout=15)

    print("=== BEFORE ===")
    for t in ("clients", "cases", "documents"):
        print(f"cloud public.{t}={count_table(src, 'public', t)}")
        print(f"yc    public.{t}={count_table(dst, 'public', t)}")
    if table_exists(src, "auth", "users"):
        print(f"cloud auth.users={count_table(src, 'auth', 'users')}")
    if table_exists(dst, "auth", "users"):
        print(f"yc    auth.users={count_table(dst, 'auth', 'users')}")

    with dst.cursor() as cur:
        cur.execute("select pg_advisory_lock(42016003)")
        # wipe app data (keep schema)
        cur.execute("TRUNCATE TABLE public.clients CASCADE")
        # auth: remove non-system users (keep if needed)
        if table_exists(dst, "auth", "users"):
            cur.execute("TRUNCATE TABLE auth.refresh_tokens CASCADE")
            cur.execute("TRUNCATE TABLE auth.sessions CASCADE")
            cur.execute("TRUNCATE TABLE auth.identities CASCADE")
            cur.execute("TRUNCATE TABLE auth.users CASCADE")
        dst.commit()

    print("=== COPY public ===")
    total = 0
    for table in COPY_ORDER:
        if not table_exists(src, "public", table):
            print(f"skip missing cloud {table}")
            continue
        if not table_exists(dst, "public", table):
            print(f"skip missing yc {table}")
            continue
        n = copy_table(src, dst, "public", table)
        dst.commit()
        print(f"copied public.{table} rows~{n}")
        total += n

    print("=== COPY auth ===")
    for table in ("users", "identities", "sessions", "refresh_tokens", "mfa_factors", "mfa_challenges", "one_time_tokens"):
        if table_exists(src, "auth", table) and table_exists(dst, "auth", table):
            try:
                n = copy_table(src, dst, "auth", table)
                dst.commit()
                print(f"copied auth.{table} rows~{n}")
            except Exception as e:
                dst.rollback()
                print(f"WARN auth.{table}: {e}")

    print("=== AFTER ===")
    for t in ("clients", "cases", "documents"):
        print(f"yc public.{t}={count_table(dst, 'public', t)}")
    if table_exists(dst, "auth", "users"):
        print(f"yc auth.users={count_table(dst, 'auth', 'users')}")

    with dst.cursor() as cur:
        cur.execute("select pg_advisory_unlock(42016003)")
        dst.commit()

    src.close()
    dst.close()
    print("OK data migrated")
    print("NEXT: patch VPS env to https://supabase.proverkastaza.ru + staging keys")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print("FAIL", e, file=sys.stderr)
        raise
