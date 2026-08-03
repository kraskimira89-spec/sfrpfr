#!/usr/bin/env python3
"""Dump Cloud public(+auth) data as SQL INSERT-free COPY format files for YC import."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "secrets" / "cutover-dumps"


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


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
    "auth.sessions",
    "auth.refresh_tokens",
]


def main() -> int:
    env = load_env(ROOT / ".env")
    dsn = env["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    # Session pooler + require SSL — надёжнее для COPY, чем transaction:5432 + verify-full.
    dsn = dsn.replace(":5432/", ":6543/")
    dsn = re.sub(r"sslmode=[^&]*", "sslmode=require", dsn)
    if "sslmode=" not in dsn:
        dsn += ("&" if "?" in dsn else "?") + "sslmode=require"

    OUT.mkdir(parents=True, exist_ok=True)
    conn = psycopg.connect(dsn, connect_timeout=45)
    manifest = []
    for fq in COPY_ORDER:
        schema, table = fq.split(".", 1)
        with conn.cursor() as cur:
            cur.execute(
                """
                select 1 from information_schema.tables
                where table_schema=%s and table_name=%s
                """,
                (schema, table),
            )
            if not cur.fetchone():
                print("skip", fq)
                continue
            cur.execute(f"select count(*) from {schema}.{table}")
            n = int(cur.fetchone()[0])
        path = OUT / f"{schema}_{table}.copy"
        chunks: list[bytes] = []
        with conn.cursor() as cur:
            with cur.copy(f"COPY {schema}.{table} TO STDOUT") as copy:
                while True:
                    chunk = copy.read()
                    if not chunk:
                        break
                    chunks.append(bytes(chunk))
        path.write_bytes(b"".join(chunks))
        print(f"dump {fq} rows={n} bytes={path.stat().st_size}")
        manifest.append(f"{fq}\t{path.name}\t{n}")
    (OUT / "manifest.tsv").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    conn.close()
    print("OK", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
