-- Единый чат по делу: кабинет ↔ MAX (канал, дедуп, outbox, прочитано).

alter table public.case_messages
  add column if not exists channel_origin text not null default 'bot'
    check (channel_origin in ('cabinet', 'max', 'admin', 'bot')),
  add column if not exists external_message_id text,
  add column if not exists updated_at timestamptz not null default now(),
  add column if not exists delivered_at timestamptz,
  add column if not exists read_at_client timestamptz,
  add column if not exists read_at_staff timestamptz;

create unique index if not exists case_messages_external_message_id_uidx
  on public.case_messages (external_message_id)
  where external_message_id is not null;

create index if not exists case_messages_case_unread_client_idx
  on public.case_messages (case_id, created_at)
  where read_at_client is null and author_kind in ('staff', 'system', 'expert', 'operator');

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

-- Outbox только через service role (FastAPI).
revoke all on public.case_chat_outbox from anon, authenticated;
