-- B2C schema + RLS for SFRFR
-- Clients see own cases; experts see assigned cases; service_role bypasses RLS (backend only).

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

create table public.clients (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users (id) on delete set null,
  full_name text not null,
  phone text,
  email text,
  created_at timestamptz not null default now()
);

create table public.cases (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete restrict,
  crm_external_id text,
  pipeline_status text not null default 'intake',
  b2c_status text not null default 'lead',
  first_contact_at timestamptz not null default now(),
  expert_user_id uuid references auth.users (id) on delete set null,
  segment text,
  region_bucket text,
  problem_type text,
  created_at timestamptz not null default now()
);

create index cases_client_id_idx on public.cases (client_id);
create index cases_expert_user_id_idx on public.cases (expert_user_id);
create index cases_b2c_status_idx on public.cases (b2c_status);
create unique index cases_crm_external_id_uidx on public.cases (crm_external_id)
  where crm_external_id is not null;

create table public.consents (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  version text not null,
  accepted_at timestamptz not null default now(),
  ip inet,
  user_agent text
);

create table public.documents (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  storage_path text not null,
  doc_type text,
  uploaded_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now()
);

create index documents_case_id_idx on public.documents (case_id);

create table public.checklist_items (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  title text not null,
  item_type text not null,
  owner text not null check (owner in ('client', 'expert')),
  due_at timestamptz,
  status text not null default 'open',
  note text,
  sort_order int not null default 0
);

create index checklist_items_case_id_idx on public.checklist_items (case_id);

create table public.orders (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  package_code text not null check (package_code in ('DIAG', 'ACCOMP', 'SF_LUMP', 'SF_MONTH')),
  amount_rub numeric(12, 2) not null check (amount_rub >= 0),
  status text not null default 'pending',
  created_at timestamptz not null default now()
);

create index orders_case_id_idx on public.orders (case_id);

create table public.payments (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders (id) on delete cascade,
  provider text,
  provider_payment_id text,
  status text not null,
  fiscal_status text,
  paid_at timestamptz
);

create index payments_order_id_idx on public.payments (order_id);

create table public.result_evidence (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  monthly_before_rub numeric(12, 2),
  monthly_after_rub numeric(12, 2),
  lump_sum_rub numeric(12, 2),
  result_effective_at date,
  confirmed_by uuid references auth.users (id) on delete set null,
  confirmed_at timestamptz,
  document_id uuid references public.documents (id) on delete set null
);

create index result_evidence_case_id_idx on public.result_evidence (case_id);

create table public.communications (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  channel text not null,
  template_code text,
  sent_at timestamptz not null default now(),
  payload jsonb
);

create index communications_case_id_idx on public.communications (case_id);

create table public.access_audit (
  id bigserial primary key,
  actor_id uuid,
  case_id uuid,
  action text not null,
  at timestamptz not null default now()
);

create table public.contract_acceptances (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  offer_version text not null,
  order_id uuid references public.orders (id) on delete set null,
  accepted_at timestamptz not null default now(),
  acceptance_meta jsonb
);

-- ---------------------------------------------------------------------------
-- Helper: ownership checks (SECURITY INVOKER — respects RLS of caller)
-- ---------------------------------------------------------------------------

create or replace function public.is_case_client(p_case_id uuid)
returns boolean
language sql
stable
security invoker
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

create or replace function public.is_case_expert(p_case_id uuid)
returns boolean
language sql
stable
security invoker
set search_path = public
as $$
  select exists (
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
security invoker
set search_path = public
as $$
  select public.is_case_client(p_case_id) or public.is_case_expert(p_case_id);
$$;

revoke all on function public.is_case_client(uuid) from public;
revoke all on function public.is_case_expert(uuid) from public;
revoke all on function public.can_access_case(uuid) from public;
grant execute on function public.is_case_client(uuid) to authenticated;
grant execute on function public.is_case_expert(uuid) to authenticated;
grant execute on function public.can_access_case(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

alter table public.clients enable row level security;
alter table public.cases enable row level security;
alter table public.consents enable row level security;
alter table public.documents enable row level security;
alter table public.checklist_items enable row level security;
alter table public.orders enable row level security;
alter table public.payments enable row level security;
alter table public.result_evidence enable row level security;
alter table public.communications enable row level security;
alter table public.access_audit enable row level security;
alter table public.contract_acceptances enable row level security;

-- clients
create policy clients_select_own
  on public.clients for select to authenticated
  using ((select auth.uid()) = user_id);

create policy clients_update_own
  on public.clients for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy clients_insert_own
  on public.clients for insert to authenticated
  with check ((select auth.uid()) = user_id);

-- cases
create policy cases_select_own_or_expert
  on public.cases for select to authenticated
  using (
    client_id in (select id from public.clients where user_id = (select auth.uid()))
    or expert_user_id = (select auth.uid())
  );

create policy cases_update_own_or_expert
  on public.cases for update to authenticated
  using (
    client_id in (select id from public.clients where user_id = (select auth.uid()))
    or expert_user_id = (select auth.uid())
  )
  with check (
    client_id in (select id from public.clients where user_id = (select auth.uid()))
    or expert_user_id = (select auth.uid())
  );

create policy cases_insert_own_client
  on public.cases for insert to authenticated
  with check (
    client_id in (select id from public.clients where user_id = (select auth.uid()))
  );

-- Generic case-scoped policies
create policy consents_select on public.consents for select to authenticated
  using (public.can_access_case(case_id));
create policy consents_insert on public.consents for insert to authenticated
  with check (public.is_case_client(case_id));

create policy documents_select on public.documents for select to authenticated
  using (public.can_access_case(case_id));
create policy documents_insert on public.documents for insert to authenticated
  with check (public.can_access_case(case_id));
create policy documents_update on public.documents for update to authenticated
  using (public.can_access_case(case_id))
  with check (public.can_access_case(case_id));

create policy checklist_select on public.checklist_items for select to authenticated
  using (public.can_access_case(case_id));
create policy checklist_insert on public.checklist_items for insert to authenticated
  with check (public.can_access_case(case_id));
create policy checklist_update on public.checklist_items for update to authenticated
  using (public.can_access_case(case_id))
  with check (public.can_access_case(case_id));

create policy orders_select on public.orders for select to authenticated
  using (public.can_access_case(case_id));
create policy orders_insert on public.orders for insert to authenticated
  with check (public.is_case_client(case_id) or public.is_case_expert(case_id));

create policy payments_select on public.payments for select to authenticated
  using (
    exists (
      select 1 from public.orders o
      where o.id = order_id and public.can_access_case(o.case_id)
    )
  );

create policy result_evidence_select on public.result_evidence for select to authenticated
  using (public.can_access_case(case_id));
create policy result_evidence_insert on public.result_evidence for insert to authenticated
  with check (public.can_access_case(case_id));
create policy result_evidence_update on public.result_evidence for update to authenticated
  using (public.is_case_expert(case_id) or public.is_case_client(case_id))
  with check (public.is_case_expert(case_id) or public.is_case_client(case_id));

create policy communications_select on public.communications for select to authenticated
  using (public.can_access_case(case_id));

create policy contract_acceptances_select on public.contract_acceptances for select to authenticated
  using (public.can_access_case(case_id));
create policy contract_acceptances_insert on public.contract_acceptances for insert to authenticated
  with check (public.is_case_client(case_id));

-- access_audit: read own case audits; inserts via service_role / backend
create policy access_audit_select on public.access_audit for select to authenticated
  using (case_id is not null and public.can_access_case(case_id));

-- ---------------------------------------------------------------------------
-- Grants for Data API (tables stay locked down by RLS)
-- ---------------------------------------------------------------------------

grant usage on schema public to anon, authenticated;

grant select, insert, update on public.clients to authenticated;
grant select, insert, update on public.cases to authenticated;
grant select, insert on public.consents to authenticated;
grant select, insert, update on public.documents to authenticated;
grant select, insert, update on public.checklist_items to authenticated;
grant select, insert on public.orders to authenticated;
grant select on public.payments to authenticated;
grant select, insert, update on public.result_evidence to authenticated;
grant select on public.communications to authenticated;
grant select, insert on public.contract_acceptances to authenticated;
grant select on public.access_audit to authenticated;

-- anon: no direct table access (leads go through backend with service_role)
revoke all on public.clients from anon;
revoke all on public.cases from anon;
revoke all on public.documents from anon;

-- ---------------------------------------------------------------------------
-- Storage: private bucket pension-docs
-- ---------------------------------------------------------------------------

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'pension-docs',
  'pension-docs',
  false,
  52428800,
  array['application/pdf', 'image/jpeg', 'image/png', 'image/webp', 'image/tiff']
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- Path convention: {case_id}/{document_id}/filename
create policy pension_docs_select on storage.objects
  for select to authenticated
  using (
    bucket_id = 'pension-docs'
    and public.can_access_case((storage.foldername(name))[1]::uuid)
  );

create policy pension_docs_insert on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'pension-docs'
    and public.can_access_case((storage.foldername(name))[1]::uuid)
  );

create policy pension_docs_update on storage.objects
  for update to authenticated
  using (
    bucket_id = 'pension-docs'
    and public.can_access_case((storage.foldername(name))[1]::uuid)
  )
  with check (
    bucket_id = 'pension-docs'
    and public.can_access_case((storage.foldername(name))[1]::uuid)
  );
