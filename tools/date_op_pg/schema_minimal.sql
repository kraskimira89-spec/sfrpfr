-- Минимальная схема для PG-интеграции date-op / snapshot CAS.
-- Источник колонок: supabase/migrations/20260722122128_b2c_schema_rls.sql
-- и 20260723094202_secure_roles_case_data.sql (+ analysis_notes).
-- Без auth.users / RLS / prod-данных. Только local/CI контейнер.

create extension if not exists "pgcrypto";

create table if not exists public.clients (
  id uuid primary key,
  full_name text not null,
  phone text,
  email text,
  created_at timestamptz not null default now()
);

create table if not exists public.cases (
  id uuid primary key,
  client_id uuid not null references public.clients (id) on delete restrict,
  b2c_status text not null default 'lead',
  created_at timestamptz not null default now()
);

create table if not exists public.case_pipeline_data (
  case_id uuid primary key references public.cases (id) on delete cascade,
  ocr_texts jsonb not null default '[]'::jsonb,
  classifications jsonb not null default '[]'::jsonb,
  ils_periods jsonb not null default '[]'::jsonb,
  labor_periods jsonb not null default '[]'::jsonb,
  findings jsonb not null default '[]'::jsonb,
  draft jsonb,
  analysis_notes text,
  error text,
  updated_at timestamptz not null default now()
);
