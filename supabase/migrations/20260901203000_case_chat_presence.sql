-- Активность интерфейсов единого чата для подавления дублирующих уведомлений.

create table if not exists public.case_chat_presence (
  case_id uuid not null references public.cases (id) on delete cascade,
  channel text not null check (channel in ('cabinet', 'max')),
  last_active_at timestamptz not null default now(),
  primary key (case_id, channel)
);

create index if not exists case_chat_presence_active_idx
  on public.case_chat_presence (case_id, last_active_at desc);

alter table public.case_chat_presence enable row level security;

-- Активность обновляет только FastAPI service role; клиенту таблица не открывается.
revoke all on public.case_chat_presence from anon, authenticated;
