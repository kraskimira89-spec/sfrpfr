-- Outbox проекции дела → Яндекс Трекер (без ПДн в payload).
-- Worker читает pending и обновляет карточку; ошибка Трекера не откатывает бизнес-факт.

create table if not exists public.tracker_sync_outbox (
  id uuid primary key default gen_random_uuid(),
  event_id text not null,
  event_type text not null,
  case_id uuid references public.cases (id) on delete set null,
  case_ref text not null,
  issue_key text not null,
  case_revision integer not null default 0,
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'pending',
  attempts integer not null default 0,
  last_error text,
  origin text not null default 'app',
  created_at timestamptz not null default now(),
  processed_at timestamptz,
  constraint tracker_sync_outbox_status_chk check (
    status in ('pending', 'done', 'error', 'dead')
  ),
  constraint tracker_sync_outbox_event_id_uidx unique (event_id)
);

comment on table public.tracker_sync_outbox is
  'Outbox синхронизации проекции дела в Яндекс Трекер. Без ПДн.';

create index if not exists tracker_sync_outbox_pending_idx
  on public.tracker_sync_outbox (status, created_at)
  where status = 'pending';

create index if not exists tracker_sync_outbox_case_ref_idx
  on public.tracker_sync_outbox (case_ref);

alter table public.tracker_sync_outbox enable row level security;

revoke all on public.tracker_sync_outbox from anon, authenticated;
grant all on public.tracker_sync_outbox to service_role;
