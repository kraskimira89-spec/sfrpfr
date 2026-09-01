-- ТЗ-13: очередь ingest v2, карантин/антивирус и артефакты постраничного OCR.

alter table public.documents
  add column if not exists antivirus_status text not null default 'not_configured',
  add column if not exists security_checked_at timestamptz,
  add column if not exists security_reason text,
  add column if not exists ingest_review_required boolean not null default false,
  add column if not exists ingest_artifact_path text,
  add column if not exists ingest_manifest_path text,
  add column if not exists ingest_engine text,
  add column if not exists duplicate_checksum boolean not null default false;

create index if not exists documents_ingest_review_idx
  on public.documents (case_id, ingest_review_required)
  where ingest_review_required = true;

create table if not exists public.document_ingest_jobs (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  document_id uuid not null references public.documents (id) on delete cascade,
  job_type text not null default 'ingest',
  status text not null default 'queued'
    check (status in ('queued', 'running', 'completed', 'needs_review', 'failed')),
  attempts integer not null default 0,
  max_attempts integer not null default 3,
  progress_percent integer not null default 0,
  current_stage text,
  last_error text,
  locked_by text,
  locked_at timestamptz,
  available_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (document_id, job_type)
);

create index if not exists document_ingest_jobs_queue_idx
  on public.document_ingest_jobs (status, available_at, created_at);
create index if not exists document_ingest_jobs_case_idx
  on public.document_ingest_jobs (case_id);

alter table public.document_ingest_jobs enable row level security;

create policy document_ingest_jobs_select on public.document_ingest_jobs
  for select to authenticated
  using (public.can_access_case(case_id));

create policy document_ingest_jobs_insert on public.document_ingest_jobs
  for insert to authenticated
  with check (public.can_access_case(case_id));

create policy document_ingest_jobs_update on public.document_ingest_jobs
  for update to authenticated
  using (public.can_access_case(case_id))
  with check (public.can_access_case(case_id));

grant select, insert, update on public.document_ingest_jobs to authenticated;

alter table public.checklist_items
  add column if not exists allow_multiple boolean not null default false,
  add column if not exists min_count integer not null default 0,
  add column if not exists max_count integer,
  add column if not exists display_group text;

