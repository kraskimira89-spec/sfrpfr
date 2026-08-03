import re
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

env = {}
for line in Path(".env").read_text(encoding="utf-8").splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, _, v = s.partition("=")
    env[k.strip()] = v.strip().strip('"').strip("'")
dsn = env["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
dsn = re.sub(r":\d+/", ":6543/", dsn)
dsn = re.sub(r"sslmode=[^&]*", "sslmode=require", dsn)
if "sslmode=" not in dsn:
    dsn += ("&" if "?" in dsn else "?") + "sslmode=require"

with psycopg.connect(dsn, connect_timeout=45, row_factory=dict_row) as c:
    with c.cursor() as cur:
        cur.execute(
            """
            select column_name from information_schema.columns
            where table_schema='auth' and table_name='users' and is_generated='NEVER'
            order by ordinal_position
            """
        )
        cols = [r["column_name"] for r in cur.fetchall()]
        for i, col in enumerate(cols, 1):
            print(f"try col {i}/{len(cols)} {col}", flush=True)
            cur.execute(f'select "{col}" from auth.users limit 1')
            row = cur.fetchone()
            v = row[col] if row else None
            print(f"  ok type={type(v).__name__} len={len(str(v)) if v is not None else 0}", flush=True)
print("ALL_OK", flush=True)
