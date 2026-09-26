"""Read-only сравнение старой и новой Supabase БД по первичным ключам.

Запуск на VPS: DSN берётся из DATABASE_URL (старая БД), новая — тот же DSN
с заменой хоста на NEW_HOST. Ничего не пишет.
"""

from __future__ import annotations

import os
import sys

import psycopg

OLD_HOST = "51.250.13.240"
NEW_HOST = "51.250.69.237"
SCHEMAS = ("public", "auth", "storage")
SKIP = {
    ("auth", "sessions"),
    ("auth", "refresh_tokens"),
    ("auth", "mfa_amr_claims"),
    ("auth", "flow_state"),
    ("auth", "audit_log_entries"),
    ("auth", "one_time_tokens"),
}

PK_SQL = """
select n.nspname, c.relname,
       array_agg(a.attname order by array_position(i.indkey::int2[], a.attnum))
from pg_index i
join pg_class c on c.oid = i.indrelid
join pg_namespace n on n.oid = c.relnamespace
join pg_attribute a on a.attrelid = c.oid and a.attnum = any(i.indkey)
where i.indisprimary and n.nspname = any(%s) and c.relkind = 'r'
group by 1, 2 order by 1, 2
"""


def rows(conn: psycopg.Connection, schema: str, table: str, pk: list[str]) -> dict:
    cols = ", ".join(f'"{c}"::text' for c in pk)
    sql = f'select {cols}, md5(t::text) from "{schema}"."{table}" t'
    return {tuple(r[:-1]): r[-1] for r in conn.execute(sql)}


def main() -> int:
    dsn = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    if OLD_HOST not in dsn:
        print("DATABASE_URL не указывает на старую ВМ — стоп")
        return 1
    old = psycopg.connect(dsn, autocommit=True)
    new = psycopg.connect(dsn.replace(OLD_HOST, NEW_HOST), autocommit=True)
    tables = old.execute(PK_SQL, (list(SCHEMAS),)).fetchall()
    print(f"{'table':45} {'old':>6} {'new':>6} {'old_only':>8} {'new_only':>8} {'diff':>5}")
    for schema, table, pk in tables:
        if (schema, table) in SKIP:
            continue
        try:
            a = rows(old, schema, table, pk)
            b = rows(new, schema, table, pk)
        except psycopg.Error as exc:
            print(f"{schema}.{table}: ERROR {type(exc).__name__}")
            continue
        old_only = a.keys() - b.keys()
        new_only = b.keys() - a.keys()
        diff = [k for k in a.keys() & b.keys() if a[k] != b[k]]
        if old_only or new_only or diff:
            print(
                f"{schema + '.' + table:45} {len(a):6} {len(b):6} "
                f"{len(old_only):8} {len(new_only):8} {len(diff):5}"
            )
            if diff and len(diff) <= 5:
                print(f"    diff pk: {diff}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
