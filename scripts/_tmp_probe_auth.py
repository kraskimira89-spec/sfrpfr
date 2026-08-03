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
            select column_name, is_generated
            from information_schema.columns
            where table_schema='auth' and table_name='users'
            order by ordinal_position
            """
        )
        cols = cur.fetchall()
        print("ncols", len(cols), flush=True)
        for col in cols:
            print(col["column_name"], col["is_generated"], flush=True)
        cur.execute("select id, email, role from auth.users")
        rows = cur.fetchall()
        print("users", len(rows), flush=True)
