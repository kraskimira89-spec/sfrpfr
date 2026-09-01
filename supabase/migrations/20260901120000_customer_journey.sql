-- Путь клиента: сценарии дела, расширенные требования к документам, LABOR_WORD.

create table if not exists public.case_scenarios (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  scenario_code text not null,
  source text not null default 'client' check (source in ('client', 'staff', 'max_intake')),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  unique (case_id, scenario_code)
);

create index if not exists case_scenarios_case_id_idx on public.case_scenarios (case_id);

alter table public.checklist_items
  add column if not exists requirement_code text,
  add column if not exists scenario_code text,
  add column if not exists category text,
  add column if not exists reason_for_request text,
  add column if not exists is_required_now boolean not null default true,
  add column if not exists consent_required boolean not null default false,
  add column if not exists requested_by uuid references auth.users (id) on delete set null,
  add column if not exists requested_at timestamptz,
  add column if not exists unavailable_reason text,
  add column if not exists period_from date,
  add column if not exists period_to date;

alter table public.orders drop constraint if exists orders_package_code_check;
alter table public.orders add constraint orders_package_code_check
  check (package_code in ('DIAG', 'ACCOMP', 'SF_LUMP', 'SF_MONTH', 'LABOR_WORD'));

alter table public.cases
  add column if not exists labor_transcription_status text,
  add column if not exists labor_transcription_pages integer,
  add column if not exists labor_transcription_estimate_rub integer;

alter table public.case_scenarios enable row level security;

create policy case_scenarios_select on public.case_scenarios
  for select to authenticated
  using (public.can_access_case(case_id));

create policy case_scenarios_insert on public.case_scenarios
  for insert to authenticated
  with check (public.can_access_case(case_id));

create policy case_scenarios_update on public.case_scenarios
  for update to authenticated
  using (public.can_access_case(case_id))
  with check (public.can_access_case(case_id));

grant select, insert, update on public.case_scenarios to authenticated;
