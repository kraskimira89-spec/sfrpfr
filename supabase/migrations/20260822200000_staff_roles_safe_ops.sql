-- P0: статусы сотрудников, приглашения, журнал staff_access_audit.

alter table public.staff_roles
  add column if not exists status text not null default 'active',
  add column if not exists display_name text,
  add column if not exists invited_at timestamptz,
  add column if not exists invite_expires_at timestamptz,
  add column if not exists invite_token_hash text,
  add column if not exists suspended_at timestamptz,
  add column if not exists last_sign_in_at timestamptz;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'staff_roles_status_check'
  ) then
    alter table public.staff_roles
      add constraint staff_roles_status_check
      check (status in ('active', 'invited', 'suspended', 'archived'));
  end if;
end $$;

update public.staff_roles
set status = 'active'
where status is null or status = '';

create index if not exists staff_roles_status_idx
  on public.staff_roles (status);

create index if not exists staff_roles_invite_token_hash_idx
  on public.staff_roles (invite_token_hash)
  where invite_token_hash is not null;

create table if not exists public.staff_access_audit (
  id bigserial primary key,
  at timestamptz not null default now(),
  actor_id uuid,
  target_user_id uuid,
  event text not null,
  old_role text,
  new_role text,
  old_status text,
  new_status text,
  result text not null default 'success'
    check (result in ('success', 'denied', 'error')),
  ip text,
  user_agent text,
  meta jsonb not null default '{}'::jsonb
);

create index if not exists staff_access_audit_target_idx
  on public.staff_access_audit (target_user_id, at desc);

create index if not exists staff_access_audit_actor_idx
  on public.staff_access_audit (actor_id, at desc);

alter table public.staff_access_audit enable row level security;

-- Записи только через service role (backend). Authenticated admin читает через API.
drop policy if exists staff_access_audit_admin_select on public.staff_access_audit;
create policy staff_access_audit_admin_select
  on public.staff_access_audit
  for select
  to authenticated
  using (private.is_staff('admin'));

grant select on public.staff_access_audit to authenticated;
grant all on public.staff_access_audit to service_role;
grant usage, select on sequence public.staff_access_audit_id_seq to service_role;
