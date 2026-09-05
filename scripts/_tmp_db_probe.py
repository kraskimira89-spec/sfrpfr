import os
from pathlib import Path

import psycopg

for line in Path(".env").read_text(encoding="utf-8").splitlines():
    if line.startswith("DATABASE_URL="):
        os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip()
        break

dsn = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
with psycopg.connect(dsn, connect_timeout=25) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "select to_regclass('public.case_chat_outbox'), "
            "to_regclass('public.case_messages')"
        )
        print("regclass", cur.fetchone())
        cur.execute(
            """
            select table_name from information_schema.tables
            where table_schema='public' and table_name like 'case_chat%'
            order by 1
            """
        )
        print("case_chat_*", [r[0] for r in cur.fetchall()])
        cur.execute(
            """
            select count(*) from clients
            where nullif(trim(max_user_id), '') is not null
            """
        )
        print("clients_max", cur.fetchone()[0])
