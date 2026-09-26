"""Перенос строк, которые есть только в старой Supabase БД, в новую.

Запуск на VPS (DATABASE_URL указывает на старую ВМ):
  python db_merge_old_into_new.py            # транзакция + ROLLBACK (проверка)
  python db_merge_old_into_new.py --commit   # транзакция + COMMIT
"""

from __future__ import annotations

import os
import sys

import psycopg
from psycopg.types.json import Jsonb

OLD_HOST = "51.250.13.240"
NEW_HOST = "51.250.69.237"
# Порядок по внешним ключам; access_audit — bigserial, id берём из последовательности новой БД.
TABLES = [
    ("auth", "users", "id"),
    ("auth", "identities", "id"),
    ("public", "clients", "id"),
    ("public", "cases", "id"),
    ("public", "consents", "id"),
    ("public", "checklist_items", "id"),
    ("public", "case_messages", "id"),
    ("public", "delivery_events", "id"),
]
AUDIT_NEW_ID_FROM = 677
CASE_STATUS_FIX = ("936be2ba-bdf3-4a93-8eda-4004ec543f1e", "lead", "consent_accepted")


def columns(conn: psycopg.Connection, schema: str, table: str, exclude: set[str]) -> list[str]:
    rows = conn.execute(
        "select column_name from information_schema.columns "
        "where table_schema=%s and table_name=%s and is_generated='NEVER' "
        "and coalesce(identity_generation,'')<>'ALWAYS' order by ordinal_position",
        (schema, table),
    ).fetchall()
    return [r[0] for r in rows if r[0] not in exclude]


def copy_missing(old, new, schema: str, table: str, pk: str) -> int:
    have = {r[0] for r in new.execute(f'select "{pk}"::text from "{schema}"."{table}"')}
    data = [
        r[1]
        for r in old.execute(f'select "{pk}"::text, row_to_json(t) from "{schema}"."{table}" t')
        if r[0] not in have
    ]
    if not data:
        return 0
    cols = ", ".join(f'"{c}"' for c in columns(new, schema, table, set()))
    cur = new.execute(
        f'insert into "{schema}"."{table}" ({cols}) '
        f'select {cols} from json_populate_recordset(null::"{schema}"."{table}", %s::json) '
        f"on conflict do nothing",
        (Jsonb(data),),
    )
    return cur.rowcount


def copy_audit(old, new) -> int:
    data = [
        r[0]
        for r in old.execute(
            "select row_to_json(t) from public.access_audit t where id >= %s order by id",
            (AUDIT_NEW_ID_FROM,),
        )
    ]
    if not data:
        return 0
    cols = ", ".join(f'"{c}"' for c in columns(new, "public", "access_audit", {"id"}))
    cur = new.execute(
        f"insert into public.access_audit ({cols}) "
        f"select {cols} from json_populate_recordset(null::public.access_audit, %s::json)",
        (Jsonb(data),),
    )
    return cur.rowcount


def main() -> int:
    commit = "--commit" in sys.argv
    dsn = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    if OLD_HOST not in dsn:
        print("DATABASE_URL не указывает на старую ВМ — стоп")
        return 1
    old = psycopg.connect(dsn, autocommit=True)
    new = psycopg.connect(dsn.replace(OLD_HOST, NEW_HOST))
    try:
        for schema, table, pk in TABLES:
            print(f"{schema}.{table}: +{copy_missing(old, new, schema, table, pk)}")
        print(f"public.access_audit: +{copy_audit(old, new)}")
        case_id, was, now = CASE_STATUS_FIX
        cur = new.execute(
            "update public.cases set b2c_status=%s where id=%s and b2c_status=%s",
            (now, case_id, was),
        )
        print(f"cases {case_id[:8]} b2c_status {was}->{now}: {cur.rowcount}")
    except Exception:
        new.rollback()
        raise
    if commit:
        new.commit()
        print("COMMIT")
    else:
        new.rollback()
        print("ROLLBACK (проверка, ничего не записано)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
