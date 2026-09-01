-- Путь клиента: группы страниц, batch-загрузка, ingest-статусы, аудит доступа.

alter table public.documents
  add column if not exists document_group_id uuid,
  add column if not exists page_index int,
  add column if not exists page_order int not null default 0,
  add column if not exists upload_batch_id uuid,
  add column if not exists upload_source text default 'cabinet',
  add column if not exists checksum_sha256 text,
  add column if not exists mime_verified text,
  add column if not exists ingest_status text not null default 'uploaded',
  add column if not exists progress_percent int not null default 0,
  add column if not exists current_stage text,
  add column if not exists progress_message text,
  add column if not exists requirement_code text,
  add column if not exists placement_suggestion jsonb,
  add column if not exists quality_report jsonb,
  add column if not exists client_declared_signed boolean not null default false,
  add column if not exists grouping_confirmed_by uuid references auth.users (id) on delete set null,
  add column if not exists page_count int,
  add column if not exists replaces_document_id uuid references public.documents (id) on delete set null;

create index if not exists documents_group_id_idx on public.documents (document_group_id);
create index if not exists documents_batch_id_idx on public.documents (upload_batch_id);
create index if not exists documents_checksum_idx on public.documents (case_id, checksum_sha256);

create table if not exists public.document_groups (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  requirement_code text,
  doc_type text,
  title text,
  page_count_expected int,
  is_page_complete boolean not null default false,
  grouping_confirmed_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now()
);

create index if not exists document_groups_case_id_idx on public.document_groups (case_id);

alter table public.document_groups enable row level security;

create policy document_groups_select on public.document_groups
  for select to authenticated
  using (public.can_access_case(case_id));

create policy document_groups_insert on public.document_groups
  for insert to authenticated
  with check (public.can_access_case(case_id));

create policy document_groups_update on public.document_groups
  for update to authenticated
  using (public.can_access_case(case_id))
  with check (public.can_access_case(case_id));

grant select, insert, update on public.document_groups to authenticated;

create table if not exists public.document_access_audit (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  document_id uuid references public.documents (id) on delete set null,
  actor_id uuid references auth.users (id) on delete set null,
  action text not null,
  created_at timestamptz not null default now()
);

create index if not exists document_access_audit_case_idx on public.document_access_audit (case_id);

alter table public.document_access_audit enable row level security;

create policy document_access_audit_select on public.document_access_audit
  for select to authenticated
  using (public.can_access_case(case_id));

create policy document_access_audit_insert on public.document_access_audit
  for insert to authenticated
  with check (public.can_access_case(case_id));

grant select, insert on public.document_access_audit to authenticated;

create table if not exists public.labor_timeline_drafts (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  document_id uuid references public.documents (id) on delete set null,
  document_group_id uuid references public.document_groups (id) on delete set null,
  employer text,
  period_from date,
  period_to date,
  position text,
  event_type text,
  source_page int,
  confidence numeric(4, 3),
  status text not null default 'draft',
  created_at timestamptz not null default now()
);

create index if not exists labor_timeline_drafts_case_idx on public.labor_timeline_drafts (case_id);

alter table public.labor_timeline_drafts enable row level security;

create policy labor_timeline_drafts_select on public.labor_timeline_drafts
  for select to authenticated
  using (public.can_access_case(case_id));

grant select on public.labor_timeline_drafts to authenticated;
