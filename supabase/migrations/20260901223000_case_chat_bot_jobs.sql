-- Очередь ответов бота: HTTP/webhook не ждут LLM.

create table if not exists public.case_chat_bot_jobs (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  message_id uuid not null references public.case_messages (id) on delete cascade,
  correlation_id text not null,
  status text not null default 'queued'
    check (status in ('queued', 'processing', 'retrying', 'completed', 'failed')),
  attempt_count int not null default 0,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  next_retry_at timestamptz,
  reply_message_id uuid references public.case_messages (id) on delete set null,
  error_category text,
  error_code_internal text,
  unique (message_id)
);

create index if not exists case_chat_bot_jobs_due_idx
  on public.case_chat_bot_jobs (status, next_retry_at, created_at)
  where status in ('queued', 'retrying', 'processing');

alter table public.case_chat_bot_jobs enable row level security;

revoke all on public.case_chat_bot_jobs from anon, authenticated;
