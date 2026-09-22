-- Реанимация: учёт сервисных касаний (без ПДн в тексте лога).
create table if not exists public.case_reactivation_touches (
  id uuid primary key default gen_random_uuid(),
  case_id uuid null references public.cases (id) on delete set null,
  client_id uuid null,
  max_user_id text null,
  basket text not null,
  touch_no int not null check (touch_no in (1, 2)),
  channel text not null default 'max',
  sent_at timestamptz null,
  created_at timestamptz not null default now()
);

create index if not exists case_reactivation_touches_case_idx
  on public.case_reactivation_touches (case_id, touch_no);

create index if not exists case_reactivation_touches_client_idx
  on public.case_reactivation_touches (client_id, touch_no)
  where client_id is not null;

create index if not exists case_reactivation_touches_max_idx
  on public.case_reactivation_touches (max_user_id, touch_no)
  where max_user_id is not null;

alter table public.case_reactivation_touches enable row level security;
revoke all on public.case_reactivation_touches from anon, authenticated;

comment on table public.case_reactivation_touches is
  'Сервисные касания реанимации CRM/orphan; без тела сообщения.';
