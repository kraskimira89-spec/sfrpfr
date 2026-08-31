-- Заявки на доступ в кабинет сотрудника (одобрение администратором по email).

create table if not exists public.staff_registration_requests (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  display_name text not null,
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected')),
  requested_at timestamptz not null default now(),
  reviewed_at timestamptz,
  meta jsonb not null default '{}'::jsonb
);

create unique index if not exists staff_registration_requests_pending_email_idx
  on public.staff_registration_requests (lower(email))
  where status = 'pending';

create index if not exists staff_registration_requests_status_idx
  on public.staff_registration_requests (status, requested_at desc);

alter table public.staff_registration_requests enable row level security;
