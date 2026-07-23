-- Secure role model, case data and Storage policies.
-- This migration supersedes broad client write policies from the initial B2C schema.

create schema if not exists private;

create table public.staff_roles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  role text not null check (role in ('operator', 'expert', 'admin')),
  created_at timestamptz not null default now()
);

create table public.case_representatives (
  case_id uuid not null references public.cases (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (case_id, user_id)
);

create table public.case_pipeline_data (
  case_id uuid primary key references public.cases (id) on delete cascade,
  ocr_texts jsonb not null default '[]'::jsonb,
  classifications jsonb not null default '[]'::jsonb,
  ils_periods jsonb not null default '[]'::jsonb,
  labor_periods jsonb not null default '[]'::jsonb,
  findings jsonb not null default '[]'::jsonb,
  draft jsonb,
  error text,
  updated_at timestamptz not null default now()
);

create table public.case_messages (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  author_user_id uuid references auth.users (id) on delete set null,
  author_kind text not null check (author_kind in ('client', 'representative', 'staff', 'system')),
  body text not null,
  created_at timestamptz not null default now()
);

create index case_representatives_user_id_idx on public.case_representatives (user_id);
create index case_messages_case_id_idx on public.case_messages (case_id, created_at);

-- These helpers run in a non-exposed schema and derive every decision from
-- auth.uid(). user_metadata is deliberately never used for authorization.
create or replace function private.is_staff(p_role text default null)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.staff_roles sr
    where sr.user_id = (select auth.uid())
      and (p_role is null or sr.role = p_role or sr.role = 'admin')
  );
$$;

create or replace function public.is_case_client(p_case_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.cases c
    join public.clients cl on cl.id = c.client_id
    where c.id = p_case_id
      and cl.user_id = (select auth.uid())
  );
$$;

create or replace function public.is_case_representative(p_case_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.case_representatives cr
    where cr.case_id = p_case_id
      and cr.user_id = (select auth.uid())
  );
$$;

create or replace function public.is_case_staff(p_case_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select private.is_staff('operator')
      or exists (
        select 1
        from public.cases c
        where c.id = p_case_id
          and c.expert_user_id = (select auth.uid())
      );
$$;

create or replace function public.can_access_case(p_case_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.is_case_client(p_case_id)
      or public.is_case_representative(p_case_id)
      or public.is_case_staff(p_case_id);
$$;

revoke all on function private.is_staff(text) from public;
revoke all on function public.is_case_client(uuid) from public;
revoke all on function public.is_case_representative(uuid) from public;
revoke all on function public.is_case_staff(uuid) from public;
revoke all on function public.can_access_case(uuid) from public;
grant execute on function private.is_staff(text) to authenticated;
grant execute on function public.is_case_client(uuid) to authenticated;
grant execute on function public.is_case_representative(uuid) to authenticated;
grant execute on function public.is_case_staff(uuid) to authenticated;
grant execute on function public.can_access_case(uuid) to authenticated;

alter table public.staff_roles enable row level security;
alter table public.case_representatives enable row level security;
alter table public.case_pipeline_data enable row level security;
alter table public.case_messages enable row level security;

-- Admin manages staff membership. Employees can read their own role only.
create policy staff_roles_select_own on public.staff_roles
  for select to authenticated
  using ((select auth.uid()) = user_id or private.is_staff('admin'));
create policy staff_roles_admin_write on public.staff_roles
  for all to authenticated
  using (private.is_staff('admin'))
  with check (private.is_staff('admin'));

create policy case_representatives_select on public.case_representatives
  for select to authenticated
  using (public.can_access_case(case_id));
create policy case_representatives_manage_staff on public.case_representatives
  for all to authenticated
  using (public.is_case_staff(case_id))
  with check (public.is_case_staff(case_id));

create policy pipeline_data_select on public.case_pipeline_data
  for select to authenticated
  using (public.can_access_case(case_id));
create policy pipeline_data_manage_staff on public.case_pipeline_data
  for all to authenticated
  using (public.is_case_staff(case_id))
  with check (public.is_case_staff(case_id));

create policy case_messages_select on public.case_messages
  for select to authenticated
  using (public.can_access_case(case_id));
create policy case_messages_insert_participant on public.case_messages
  for insert to authenticated
  with check (
    public.can_access_case(case_id)
    and author_user_id = (select auth.uid())
    and author_kind in ('client', 'representative', 'staff')
  );

-- Clients and representatives may read case data, but only staff can mutate
-- pipeline status, assignments, orders, payments and result evidence.
drop policy if exists cases_select_own_or_expert on public.cases;
drop policy if exists cases_update_own_or_expert on public.cases;
drop policy if exists cases_insert_own_client on public.cases;
create policy cases_select_participant on public.cases
  for select to authenticated
  using (public.can_access_case(id));
create policy cases_manage_staff on public.cases
  for all to authenticated
  using (public.is_case_staff(id))
  with check (public.is_case_staff(id));

drop policy if exists documents_insert on public.documents;
drop policy if exists documents_update on public.documents;
create policy documents_insert_participant on public.documents
  for insert to authenticated
  with check (
    public.can_access_case(case_id)
    and uploaded_by = (select auth.uid())
  );
create policy documents_update_staff on public.documents
  for update to authenticated
  using (public.is_case_staff(case_id))
  with check (public.is_case_staff(case_id));

drop policy if exists checklist_insert on public.checklist_items;
drop policy if exists checklist_update on public.checklist_items;
create policy checklist_manage_staff on public.checklist_items
  for all to authenticated
  using (public.is_case_staff(case_id))
  with check (public.is_case_staff(case_id));

drop policy if exists orders_insert on public.orders;
drop policy if exists result_evidence_insert on public.result_evidence;
drop policy if exists result_evidence_update on public.result_evidence;
create policy orders_manage_staff on public.orders
  for all to authenticated
  using (public.is_case_staff(case_id))
  with check (public.is_case_staff(case_id));
create policy result_evidence_manage_staff on public.result_evidence
  for all to authenticated
  using (public.is_case_staff(case_id))
  with check (public.is_case_staff(case_id));

grant select on public.staff_roles, public.case_representatives,
  public.case_pipeline_data, public.case_messages to authenticated;
grant insert on public.case_messages to authenticated;

-- Keep the existing private bucket and restrict objects by the case UUID at
-- the first path segment: {case_id}/{document_id}/filename.
drop policy if exists pension_docs_select on storage.objects;
drop policy if exists pension_docs_insert on storage.objects;
drop policy if exists pension_docs_update on storage.objects;
create policy pension_docs_select_participant on storage.objects
  for select to authenticated
  using (
    bucket_id = 'pension-docs'
    and public.can_access_case((storage.foldername(name))[1]::uuid)
  );
create policy pension_docs_insert_participant on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'pension-docs'
    and public.can_access_case((storage.foldername(name))[1]::uuid)
    and owner_id = (select auth.uid()::text)
  );
create policy pension_docs_mutate_staff on storage.objects
  for update to authenticated
  using (
    bucket_id = 'pension-docs'
    and public.is_case_staff((storage.foldername(name))[1]::uuid)
  )
  with check (
    bucket_id = 'pension-docs'
    and public.is_case_staff((storage.foldername(name))[1]::uuid)
  );
