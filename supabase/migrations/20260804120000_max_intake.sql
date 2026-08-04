-- ТЗ-20: диагностика в личном чате MAX (без свободного текста и ПДн)
create table if not exists public.max_intake (
  id uuid primary key default gen_random_uuid(),
  client_id uuid null references public.clients (id) on delete set null,
  case_id uuid null references public.cases (id) on delete set null,
  max_user_id text not null,
  goal text null check (
    goal is null
    or goal in ('check_experience', 'missing_period', 'sfr_question', 'operator')
  ),
  ils_available text null check (
    ils_available is null or ils_available in ('yes', 'no', 'unknown')
  ),
  employment_records_available text null check (
    employment_records_available is null
    or employment_records_available in ('yes', 'partial', 'no')
  ),
  device_preference text null check (
    device_preference is null or device_preference in ('max', 'web', 'help')
  ),
  status text not null default 'started' check (
    status in ('started', 'completed', 'handed_to_operator', 'abandoned')
  ),
  started_at timestamptz not null default now(),
  completed_at timestamptz null,
  updated_at timestamptz not null default now()
);

create index if not exists max_intake_max_user_id_idx on public.max_intake (max_user_id);
create index if not exists max_intake_status_idx on public.max_intake (status);
create unique index if not exists max_intake_one_started_per_user_idx
  on public.max_intake (max_user_id)
  where status = 'started';

alter table public.max_intake enable row level security;

comment on table public.max_intake is
  'Диагностика MAX-бота (ТЗ-20). Только enum-поля, без свободного текста и ПДн.';
