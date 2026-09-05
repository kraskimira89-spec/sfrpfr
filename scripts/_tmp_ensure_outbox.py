"""Try Postgres on 5432 and ensure case_chat_outbox exists."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, urlunparse

import psycopg

dsn = ""
for line in Path("/opt/sfrfr/.env").read_text(encoding="utf-8").splitlines():
    if line.startswith("DATABASE_URL="):
        dsn = line.split("=", 1)[1].strip().strip('"').strip("'")
        break
dsn = dsn.replace("postgresql+psycopg://", "postgresql://")
u = urlparse(dsn)
# prefer working port 5432
for port in (5432, 5433):
    alt = u._replace(netloc=f"{u.username}:{u.password}@{u.hostname}:{port}")
    try_dsn = urlunparse(alt)
    print("try", u.hostname, port)
    try:
        with psycopg.connect(try_dsn, connect_timeout=15) as conn:
            with conn.cursor() as cur:
                cur.execute("select current_database(), current_user")
                print("ok", cur.fetchone())
                cur.execute("select to_regclass('public.case_chat_outbox')")
                print("outbox", cur.fetchone())
                sql = Path(
                    "/opt/sfrfr/supabase/migrations/20260901194500_unified_case_chat.sql"
                )
                if not sql.is_file():
                    print("migration file missing on VPS")
                else:
                    # only create outbox if missing
                    cur.execute("select to_regclass('public.case_chat_outbox')")
                    if cur.fetchone()[0] is None:
                        print("creating outbox from migration excerpt")
                        cur.execute(
                            """
create table if not exists public.case_chat_outbox (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  message_id uuid references public.case_messages (id) on delete set null,
  max_user_id text not null,
  body text not null,
  status text not null default 'pending'
    check (status in ('pending', 'sent', 'failed')),
  attempts int not null default 0,
  last_error text,
  created_at timestamptz not null default now(),
  sent_at timestamptz
);
create index if not exists case_chat_outbox_pending_idx
  on public.case_chat_outbox (status, created_at)
  where status = 'pending';
alter table public.case_chat_outbox enable row level security;
revoke all on public.case_chat_outbox from anon, authenticated;
alter table public.case_chat_outbox
  add column if not exists attachments jsonb not null default '[]'::jsonb;
"""
                        )
                        conn.commit()
                        print("outbox created")
                    else:
                        print("outbox already exists")
                    # notify postgrest
                    try:
                        cur.execute("notify pgrst, 'reload schema'")
                        conn.commit()
                        print("notified pgrst reload schema")
                    except Exception as e:
                        print("notify failed", e)
        break
    except Exception as e:
        print("fail", port, type(e).__name__, e)
