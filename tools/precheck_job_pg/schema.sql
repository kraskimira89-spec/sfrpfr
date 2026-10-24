-- Минимальная схема для интеграционных тестов staff_document_check_jobs.
-- Без production DSN. Синтетические UUID.

create extension if not exists pgcrypto;

create table if not exists public.cases (
  id uuid primary key default gen_random_uuid(),
  flags jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  checksum_sha256 text,
  filename text,
  created_at timestamptz not null default now()
);

create table if not exists public.staff_document_check_jobs (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  job_type text not null default 'staff_docs_check',
  documents_fingerprint text not null,
  status text not null default 'queued'
    check (status in ('queued', 'running', 'completed', 'needs_action', 'failed')),
  attempts integer not null default 0,
  max_attempts integer not null default 3,
  current_stage text,
  result jsonb,
  last_error text,
  requested_by text,
  locked_by text,
  locked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  finished_at timestamptz
);

create index if not exists staff_document_check_jobs_queue_idx
  on public.staff_document_check_jobs (status, created_at)
  where status = 'queued';

create unique index if not exists staff_document_check_jobs_active_fp_uidx
  on public.staff_document_check_jobs (case_id, documents_fingerprint)
  where status in ('queued', 'running');
